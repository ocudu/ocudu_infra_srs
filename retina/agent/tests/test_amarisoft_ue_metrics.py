# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for AmarisoftUeMetricsAnalyzer.
"""

import unittest

from retina.agent.features.json_metrics.amarisoft_ue_metrics import AmarisoftUeMetricsAnalyzer

# ── Timestamps (unix epoch, 1-second steps) ───────────────────────────────────

_T0 = 1_000_000.0
_T1 = 1_000_001.0
_T2 = 1_000_002.0
_T3 = 1_000_003.0


# ── Record factory helpers ────────────────────────────────────────────────────


def make_ue_list_record(utc, ue_list):
    return {"ue_list": ue_list, "utc": utc}


def make_stats_record(cells, counters=None):
    return {
        "cells": cells,
        "counters": counters or {"messages": {}, "errors": {}},
    }


def make_ue_info(
    rnti,
    cells,
    dl_bitrate=0.0,
    ul_bitrate=0.0,
    dl_err_count=0,
    dl_retx_count=0,
    ul_retx_count=0,
    dl_mcs=None,
    ul_mcs=None,
    dl_rx_count=None,
):
    ue = {
        "rnti": rnti,
        "cells": cells,
        "dl_bitrate": dl_bitrate,
        "ul_bitrate": ul_bitrate,
        "dl_err_count": dl_err_count,
        "dl_retx_count": dl_retx_count,
        "ul_retx_count": ul_retx_count,
    }
    if dl_mcs is not None:
        ue["dl_mcs"] = dl_mcs
    if ul_mcs is not None:
        ue["ul_mcs"] = ul_mcs
    if dl_rx_count is not None:
        ue["dl_rx_count"] = dl_rx_count
    return ue


def make_cell(pci):
    return {"pci": pci}


def make_stats_cell(dl_bitrate=0.0, ul_bitrate=0.0, dl_err_count=0, dl_retx_count=0, ul_retx_count=0, dl_rx_count=None):
    cell = {
        "dl_bitrate": dl_bitrate,
        "ul_bitrate": ul_bitrate,
        "dl_err_count": dl_err_count,
        "dl_retx_count": dl_retx_count,
        "ul_retx_count": ul_retx_count,
    }
    if dl_rx_count is not None:
        cell["dl_rx_count"] = dl_rx_count
    return cell


# ── TestAmarisoftUeMetricsAnalyzerMaxMcs ─────────────────────────────────────


class TestAmarisoftUeMetricsAnalyzerMaxMcs(unittest.TestCase):
    """
    dl_max_mcs / ul_max_mcs track the highest (average) MCS reported by the UE
    across all ue_list records. The field is a float in the Amarisoft JSON
    ("average MCS used for DL/UL") and is truncated to int when stored.
    The aggregate is the maximum across all UEs seen.
    """

    def setUp(self):
        self.a = AmarisoftUeMetricsAnalyzer()

    def _process_ue(self, utc, rnti, pci, dl_mcs=None, ul_mcs=None):
        self.a.process(make_ue_list_record(utc, [make_ue_info(rnti, [make_cell(pci)], dl_mcs=dl_mcs, ul_mcs=ul_mcs)]))

    def test_single_record_single_ue(self):
        self._process_ue(_T0, rnti=1, pci=1, dl_mcs=24.0, ul_mcs=27.0)
        m = self.a.report()
        ue = next(u for u in m.ue_array if u.rnti == 1)
        self.assertEqual(ue.dl_max_mcs, 24)
        self.assertEqual(ue.ul_max_mcs, 27)
        self.assertEqual(m.aggregate.dl_max_mcs, 24)
        self.assertEqual(m.aggregate.ul_max_mcs, 27)

    def test_float_mcs_is_truncated_to_int(self):
        self._process_ue(_T0, rnti=1, pci=1, dl_mcs=24.9, ul_mcs=26.7)
        m = self.a.report()
        ue = next(u for u in m.ue_array if u.rnti == 1)
        self.assertEqual(ue.dl_max_mcs, 24)
        self.assertEqual(ue.ul_max_mcs, 26)

    def test_max_tracked_across_records(self):
        for utc, dl, ul in ((_T0, 20.0, 25.0), (_T1, 27.0, 22.0), (_T2, 15.0, 27.0)):
            self._process_ue(utc, rnti=1, pci=1, dl_mcs=dl, ul_mcs=ul)
        m = self.a.report()
        ue = next(u for u in m.ue_array if u.rnti == 1)
        self.assertEqual(ue.dl_max_mcs, 27)
        self.assertEqual(ue.ul_max_mcs, 27)

    def test_max_never_decreases(self):
        for utc, dl in ((_T0, 27.0), (_T1, 10.0), (_T2, 5.0)):
            self._process_ue(utc, rnti=1, pci=1, dl_mcs=dl)
        ue = next(u for u in self.a.report().ue_array if u.rnti == 1)
        self.assertEqual(ue.dl_max_mcs, 27)

    def test_missing_mcs_field_defaults_to_zero(self):
        self.a.process(make_ue_list_record(_T0, [make_ue_info(1, [make_cell(1)])]))
        m = self.a.report()
        ue = next(u for u in m.ue_array if u.rnti == 1)
        self.assertEqual(ue.dl_max_mcs, 0)
        self.assertEqual(ue.ul_max_mcs, 0)
        self.assertEqual(m.aggregate.dl_max_mcs, 0)
        self.assertEqual(m.aggregate.ul_max_mcs, 0)

    def test_aggregate_is_max_across_ues(self):
        self.a.process(
            make_ue_list_record(
                _T0,
                [
                    make_ue_info(1, [make_cell(1)], dl_mcs=20.0, ul_mcs=24.0),
                    make_ue_info(2, [make_cell(1)], dl_mcs=27.0, ul_mcs=15.0),
                ],
            )
        )
        m = self.a.report()
        self.assertEqual(m.aggregate.dl_max_mcs, 27)
        self.assertEqual(m.aggregate.ul_max_mcs, 24)

    def test_empty_report_aggregate_is_zero(self):
        m = self.a.report()
        self.assertEqual(m.aggregate.dl_max_mcs, 0)
        self.assertEqual(m.aggregate.ul_max_mcs, 0)

    def test_mcs_per_cell_tracked_independently(self):
        # Same RNTI on two cells gets two separate UeMetrics entries.
        self.a.process(
            make_ue_list_record(
                _T0,
                [make_ue_info(1, [make_cell(1), make_cell(2)], dl_mcs=24.0, ul_mcs=27.0)],
            )
        )
        m = self.a.report()
        self.assertEqual(len(m.ue_array), 2)
        for ue in m.ue_array:
            self.assertEqual(ue.dl_max_mcs, 24)
            self.assertEqual(ue.ul_max_mcs, 27)

    def test_aggregate_not_clobbered_by_stats_merge(self):
        # Even when a stats record is processed (which has no MCS),
        # the aggregate MCS must survive the MergeFrom call.
        self._process_ue(_T0, rnti=1, pci=1, dl_mcs=27.0, ul_mcs=27.0)
        self.a.process(
            make_stats_record(
                cells={"0": make_stats_cell(dl_bitrate=5_000_000, ul_bitrate=2_000_000)},
                counters={"messages": {"5gs_nas_pdu_session_establishment_accept": 1}, "errors": {}},
            )
        )
        m = self.a.report()
        self.assertEqual(m.aggregate.dl_max_mcs, 27)
        self.assertEqual(m.aggregate.ul_max_mcs, 27)


# ── TestAmarisoftUeMetricsAnalyzerRxDl ───────────────────────────────────────


class TestAmarisoftUeMetricsAnalyzerRxDl(unittest.TestCase):
    """
    nof_rx_dl accumulates dl_rx_count, the DL transport blocks received by the UE,
    the same way nof_ko_dl accumulates dl_retx_count + dl_err_count: summed across
    the reset-on-query "stats" calls for the aggregate, and across ue_get records
    for the per-UE entries. A missing dl_rx_count field counts as 0.
    """

    def setUp(self):
        self.a = AmarisoftUeMetricsAnalyzer()

    def test_stats_accumulated_across_calls(self):
        for rx, retx in ((10, 9), (20, 18)):
            self.a.process(make_stats_record(cells={"0": make_stats_cell(dl_rx_count=rx, dl_retx_count=retx)}))
        m = self.a.report()
        self.assertEqual(m.aggregate.nof_rx_dl, 30)
        self.assertEqual(m.aggregate.nof_ko_dl, 27)

    def test_stats_summed_across_cells(self):
        self.a.process(
            make_stats_record(
                cells={"0": make_stats_cell(dl_rx_count=7), "1": make_stats_cell(dl_rx_count=5)},
            )
        )
        self.assertEqual(self.a.report().aggregate.nof_rx_dl, 12)

    def test_stats_missing_field_defaults_to_zero(self):
        self.a.process(make_stats_record(cells={"0": make_stats_cell(dl_retx_count=3)}))
        m = self.a.report()
        self.assertEqual(m.aggregate.nof_rx_dl, 0)
        self.assertEqual(m.aggregate.nof_ko_dl, 3)

    def test_ue_get_accumulated_per_ue(self):
        for utc, rx in ((_T0, 4), (_T1, 6)):
            self.a.process(make_ue_list_record(utc, [make_ue_info(1, [make_cell(1)], dl_rx_count=rx)]))
        ue = next(u for u in self.a.report().ue_array if u.rnti == 1)
        self.assertEqual(ue.nof_rx_dl, 10)

    def test_ue_get_missing_field_defaults_to_zero(self):
        for utc in (_T0, _T1):
            self.a.process(make_ue_list_record(utc, [make_ue_info(1, [make_cell(1)])]))
        ue = next(u for u in self.a.report().ue_array if u.rnti == 1)
        self.assertEqual(ue.nof_rx_dl, 0)

    def test_selected_ues_aggregate_summed_from_ue_get(self):
        # With a UE selection the aggregate comes from the selected UEs, not from stats.
        self.a.process(
            make_ue_list_record(
                _T0,
                [
                    make_ue_info(1, [make_cell(1)], dl_rx_count=4),
                    make_ue_info(2, [make_cell(1)], dl_rx_count=6),
                ],
            )
        )
        self.a.process(make_stats_record(cells={"0": make_stats_cell(dl_rx_count=100)}))
        self.assertEqual(self.a.report({(1, 1)}).aggregate.nof_rx_dl, 4)
        self.assertEqual(self.a.report({(1, 1), (2, 1)}).aggregate.nof_rx_dl, 10)
        self.assertEqual(self.a.report().aggregate.nof_rx_dl, 100)


if __name__ == "__main__":
    unittest.main()
