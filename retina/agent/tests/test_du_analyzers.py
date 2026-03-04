# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for DU JSON metrics analyzers: GeneralMetricsAnalyzer and PerUePeakAverageAnalyzer.
"""

import unittest

from retina.agent.features.json_metrics.du_general import GeneralMetricsAnalyzer
from retina.agent.features.json_metrics.du_peak_average import PerUePeakAverageAnalyzer, _MovingAverage

# ── Timestamps ────────────────────────────────────────────────────────────────

_T0 = "2026-01-01T00:00:00.000"
_T1 = "2026-01-01T00:00:01.000"
_T2 = "2026-01-01T00:00:02.000"
_T3 = "2026-01-01T00:00:03.000"
_T4 = "2026-01-01T00:00:04.000"
_T5 = "2026-01-01T00:00:05.000"
_T6 = "2026-01-01T00:00:06.000"


# ── Record factory helpers ────────────────────────────────────────────────────


def make_record(timestamp, cells):
    return {"timestamp": timestamp, "cells": cells}


def make_cell(ue_list=None, cell_metrics=None, event_list=None):
    cell = {}
    if cell_metrics is not None:
        cell["cell_metrics"] = cell_metrics
    if ue_list is not None:
        cell["ue_list"] = ue_list
    if event_list is not None:
        cell["event_list"] = event_list
    return cell


def make_ue(
    rnti, dl_brate=0.0, ul_brate=0.0, dl_nof_nok=0, ul_nof_nok=0, pucch_f0f1=0, pucch_f2f3f4_harq=0, pucch_f2f3f4_csi=0
):
    return {
        "rnti": rnti,
        "dl_brate": dl_brate,
        "ul_brate": ul_brate,
        "dl_nof_nok": dl_nof_nok,
        "ul_nof_nok": ul_nof_nok,
        "nof_pucch_f0f1_invalid_harqs": pucch_f0f1,
        "nof_pucch_f2f3f4_invalid_harqs": pucch_f2f3f4_harq,
        "nof_pucch_f2f3f4_invalid_csis": pucch_f2f3f4_csi,
    }


def make_cell_metrics(error_indications=0, late_dl=0, late_ul=0):
    return {
        "error_indication_count": error_indications,
        "late_dl_harqs": late_dl,
        "late_ul_harqs": late_ul,
    }


def make_event(rnti, event_type):
    return {"rnti": rnti, "event_type": event_type}


# ── TestMovingAverage ─────────────────────────────────────────────────────────


class TestMovingAverage(unittest.TestCase):
    """Tests for the internal _MovingAverage helper."""

    def test_empty_returns_zero(self):
        ma = _MovingAverage(10)
        self.assertEqual(ma.get_average(), 0)

    def test_single_sample_full_window(self):
        ma = _MovingAverage(10)
        ma.add(5.0)
        self.assertAlmostEqual(ma.get_average(), 5.0)

    def test_single_sample_explicit_k(self):
        ma = _MovingAverage(10)
        ma.add(5.0)
        self.assertAlmostEqual(ma.get_average(1), 5.0)

    def test_window_clips_older_samples(self):
        # Add 1..10 to a size-5 queue; only [6,7,8,9,10] remain.
        ma = _MovingAverage(5)
        for i in range(1, 11):
            ma.add(float(i))
        self.assertAlmostEqual(ma.get_average(), 8.0)

    def test_get_average_with_explicit_k(self):
        # 10 samples in a size-30 queue; last 3 = [8,9,10] → avg=9.0
        ma = _MovingAverage(30)
        for i in range(1, 11):
            ma.add(float(i))
        self.assertAlmostEqual(ma.get_average(3), 9.0)

    def test_fewer_samples_than_k_uses_all_available(self):
        ma = _MovingAverage(30)
        ma.add(1.0)
        ma.add(2.0)
        # k=10 requested but only 2 samples → avg of [1,2] = 1.5
        self.assertAlmostEqual(ma.get_average(10), 1.5)

    def test_k_exceeds_maxlen_raises(self):
        ma = _MovingAverage(50)
        with self.assertRaises(ValueError):
            ma.get_average(51)

    def test_negative_k_raises(self):
        ma = _MovingAverage(10)
        with self.assertRaises(ValueError):
            ma.get_average(-1)


# ── TestGeneralMetricsAnalyzer — Bitrate ─────────────────────────────────────


class TestGeneralMetricsAnalyzerBitrate(unittest.TestCase):
    """
    Bitrate uses a time-weighted moving average.

    After record at T0: dl_bitrate = dl_brate (t_beginning == 0 on first sample).
    After record at T1: dl_bitrate = (prev * t_old + dl_brate * t_new) / t_beginning.
    Because t_old = (T0 - T0) = 0, the second sample completely replaces the first.
    From the third record onwards, both older and newer samples contribute.

    Note: _update_bitrate is called once per cell, all at the same timestamp within
    a record. The second cell therefore sees t_new = 0 and its value is ignored.
    Only the last cell in a record effectively contributes to each record's update.
    """

    def setUp(self):
        self.a = GeneralMetricsAnalyzer()

    def test_bitrate_single_record_single_ue(self):
        self.a.process(
            make_record(
                _T0, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=100.0, ul_brate=200.0)])]
            )
        )
        m = self.a.report()
        self.assertAlmostEqual(m.dl_bitrate, 100.0)
        self.assertAlmostEqual(m.ul_bitrate, 200.0)

    def test_bitrate_two_records_second_replaces_first(self):
        # t_old=0 on the second call → second sample overrides the first completely.
        self.a.process(
            make_record(
                _T0, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=100.0, ul_brate=200.0)])]
            )
        )
        self.a.process(
            make_record(
                _T1, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=300.0, ul_brate=50.0)])]
            )
        )
        m = self.a.report()
        self.assertAlmostEqual(m.dl_bitrate, 300.0)
        self.assertAlmostEqual(m.ul_bitrate, 50.0)

    def test_bitrate_three_records_weighted_average(self):
        # T0: dl=100 (sets first sample)
        # T1=T0+1s: dl=300 (replaces, t_old=0)
        # T3=T0+3s: dl=100 → (300×1 + 100×2) / 3 = 500/3 ≈ 166.67
        self.a.process(
            make_record(_T0, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=100.0)])])
        )
        self.a.process(
            make_record(_T1, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=300.0)])])
        )
        self.a.process(
            make_record(_T3, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=100.0)])])
        )
        self.assertAlmostEqual(self.a.report().dl_bitrate, 500.0 / 3.0, places=5)

    def test_bitrate_multiple_ues_summed_within_cell(self):
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(
                        cell_metrics=make_cell_metrics(),
                        ue_list=[make_ue(1, dl_brate=100.0), make_ue(2, dl_brate=200.0), make_ue(3, dl_brate=300.0)],
                    )
                ],
            )
        )
        self.assertAlmostEqual(self.a.report().dl_bitrate, 600.0)

    def test_bitrate_multiple_ues_multiple_records_weighted(self):
        # T0: 2 UEs, total dl=300. T1: 2 UEs, total dl=500.
        # After T1: (300×0 + 500×1) / 1 = 500 (second replaces first, t_old=0).
        # T2: 2 UEs, total dl=700.
        # After T2: (500×1 + 700×1) / 2 = 600.
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(
                        cell_metrics=make_cell_metrics(),
                        ue_list=[make_ue(1, dl_brate=100.0), make_ue(2, dl_brate=200.0)],
                    )
                ],
            )
        )
        self.a.process(
            make_record(
                _T1,
                [
                    make_cell(
                        cell_metrics=make_cell_metrics(),
                        ue_list=[make_ue(1, dl_brate=200.0), make_ue(2, dl_brate=300.0)],
                    )
                ],
            )
        )
        self.a.process(
            make_record(
                _T2,
                [
                    make_cell(
                        cell_metrics=make_cell_metrics(),
                        ue_list=[make_ue(1, dl_brate=300.0), make_ue(2, dl_brate=400.0)],
                    )
                ],
            )
        )
        self.assertAlmostEqual(self.a.report().dl_bitrate, 600.0)

    def test_bitrate_multiple_cells_summed(self):
        # UE bitrates from all cells are summed before the time-weighted update,
        # so _update_bitrate is called once per record with the aggregate total.
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(
                        cell_metrics=make_cell_metrics(),
                        ue_list=[make_ue(1, dl_brate=100.0), make_ue(2, dl_brate=200.0)],  # subtotal=300
                    ),
                    make_cell(
                        ue_list=[make_ue(3, dl_brate=300.0), make_ue(4, dl_brate=400.0)],  # subtotal=700
                    ),
                ],
            )
        )
        # After record 1: dl_bitrate = 300 + 700 = 1000 (t_beginning=0 → direct assignment).
        self.assertAlmostEqual(self.a.report().dl_bitrate, 1000.0)

        self.a.process(
            make_record(
                _T1,
                [
                    make_cell(
                        cell_metrics=make_cell_metrics(),
                        ue_list=[make_ue(1, dl_brate=100.0), make_ue(2, dl_brate=200.0)],  # subtotal=300
                    ),
                    make_cell(
                        ue_list=[make_ue(3, dl_brate=300.0), make_ue(4, dl_brate=400.0)],  # subtotal=700
                    ),
                ],
            )
        )
        # After record 2: total=1000, same as before → (1000×0 + 1000×1) / 1 = 1000.
        self.assertAlmostEqual(self.a.report().dl_bitrate, 1000.0)

    def test_bitrate_empty_ue_list_before_first_connection(self):
        # A record with no cell_metrics and an empty ue_list is skipped entirely.
        self.a.process(make_record(_T0, [make_cell(ue_list=[])]))
        # Time has not been initialized; next record sets bitrate directly.
        self.a.process(
            make_record(_T1, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=500.0)])])
        )
        self.assertAlmostEqual(self.a.report().dl_bitrate, 500.0)

    def test_bitrate_empty_at_start_and_end(self):
        # Empty metrics - this one is ignored
        self.a.process(make_record(_T0, [make_cell(ue_list=[])]))
        self.assertAlmostEqual(self.a.report().dl_bitrate, 0)

        # Empty metrics - This will be the start time to calculate the bitrate (because the next report is not empty)
        self.a.process(make_record(_T1, [make_cell(ue_list=[])]))
        self.assertAlmostEqual(self.a.report().dl_bitrate, 0)

        # First record with values - Start time to calculate the bitrate is previous report (T1)
        self.a.process(
            make_record(_T3, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=50.0)])])
        )
        self.assertAlmostEqual(self.a.report().dl_bitrate, 50.0)

        # Second record - ((T3-T1)*50 + (T4-T3)*500) / (T4-T1) = 600/3 = 200
        self.a.process(
            make_record(_T4, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=500.0)])])
        )
        self.assertAlmostEqual(self.a.report().dl_bitrate, 200.0)

        # Third record - ((T3-T1)*50 + (T4-T3) * 500) / (T5-T1) = 1200/4 = 300
        self.a.process(
            make_record(_T5, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_brate=600.0)])])
        )
        self.assertAlmostEqual(self.a.report().dl_bitrate, 300.0)

        # Empty record at the end - NOT ignored - ((T3-T1)*50 + (T4-T3) * 500) / (T6-T1) = 1200/5 = 240
        self.a.process(make_record(_T6, [make_cell(ue_list=[])]))
        self.assertAlmostEqual(self.a.report().dl_bitrate, 240.0)

    def test_bitrate_zero_when_only_cell_metrics_no_ue_list(self):
        self.a.process(make_record(_T0, [make_cell(cell_metrics=make_cell_metrics())]))
        self.assertAlmostEqual(self.a.report().dl_bitrate, 0.0)


# ── TestGeneralMetricsAnalyzer — KOs ─────────────────────────────────────────


class TestGeneralMetricsAnalyzerKOs(unittest.TestCase):
    """nof_ko_dl / nof_ko_ul are cumulative sums across all UEs and records."""

    def setUp(self):
        self.a = GeneralMetricsAnalyzer()

    def test_ko_from_single_ue(self):
        self.a.process(
            make_record(
                _T0, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_nof_nok=3, ul_nof_nok=5)])]
            )
        )
        m = self.a.report()
        self.assertEqual(m.nof_ko_dl, 3)
        self.assertEqual(m.nof_ko_ul, 5)

    def test_ko_multiple_ues_summed_within_record(self):
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(
                        cell_metrics=make_cell_metrics(),
                        ue_list=[make_ue(1, dl_nof_nok=1), make_ue(2, dl_nof_nok=2), make_ue(3, dl_nof_nok=3)],
                    )
                ],
            )
        )
        self.assertEqual(self.a.report().nof_ko_dl, 6)

    def test_ko_accumulates_across_records(self):
        for ts in (_T0, _T1):
            self.a.process(
                make_record(
                    ts, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_nof_nok=5, ul_nof_nok=2)])]
                )
            )
        m = self.a.report()
        self.assertEqual(m.nof_ko_dl, 10)
        self.assertEqual(m.nof_ko_ul, 4)

    def test_ko_multiple_cells_summed(self):
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, dl_nof_nok=5)]),
                    make_cell(ue_list=[make_ue(2, dl_nof_nok=7)]),
                ],
            )
        )
        self.assertEqual(self.a.report().nof_ko_dl, 12)

    def test_ko_multiple_ues_multiple_cells_multiple_records(self):
        # 2 cells × 2 UEs each × 2 records, each nok=1 → total = 2×2×2 = 8
        for ts in (_T0, _T1):
            self.a.process(
                make_record(
                    ts,
                    [
                        make_cell(
                            cell_metrics=make_cell_metrics(),
                            ue_list=[make_ue(1, dl_nof_nok=1), make_ue(2, dl_nof_nok=1)],
                        ),
                        make_cell(ue_list=[make_ue(3, dl_nof_nok=1), make_ue(4, dl_nof_nok=1)]),
                    ],
                )
            )
        self.assertEqual(self.a.report().nof_ko_dl, 8)


# ── TestGeneralMetricsAnalyzer — Error indications ───────────────────────────


class TestGeneralMetricsAnalyzerErrorIndications(unittest.TestCase):
    """
    The first cell_metrics report is skipped to discard a spurious error
    the DU emits at startup. All subsequent records are accumulated.
    """

    def setUp(self):
        self.a = GeneralMetricsAnalyzer()

    def _record(self, ts, errors):
        return make_record(
            ts, [make_cell(cell_metrics=make_cell_metrics(error_indications=errors), ue_list=[make_ue(1)])]
        )

    def test_first_record_always_skipped(self):
        self.a.process(self._record(_T0, 99))
        self.assertEqual(self.a.report().nof_error_indications, 0)

    def test_second_record_counted(self):
        self.a.process(self._record(_T0, 99))
        self.a.process(self._record(_T1, 3))
        self.assertEqual(self.a.report().nof_error_indications, 3)

    def test_accumulates_across_records(self):
        self.a.process(self._record(_T0, 0))
        self.a.process(self._record(_T1, 3))
        self.a.process(self._record(_T2, 5))
        self.assertEqual(self.a.report().nof_error_indications, 8)


# ── TestGeneralMetricsAnalyzer — Late HARQs ──────────────────────────────────


class TestGeneralMetricsAnalyzerLateHarqs(unittest.TestCase):
    """max_late_dl_harqs / max_late_ul_harqs are running maximums."""

    def setUp(self):
        self.a = GeneralMetricsAnalyzer()

    def test_max_late_dl_harqs(self):
        for ts, late_dl in ((_T0, 10), (_T1, 30), (_T2, 5)):
            self.a.process(
                make_record(ts, [make_cell(cell_metrics=make_cell_metrics(late_dl=late_dl), ue_list=[make_ue(1)])])
            )
        self.assertEqual(self.a.report().max_late_dl_harqs, 30)

    def test_max_late_ul_harqs(self):
        for ts, late_ul in ((_T0, 5), (_T1, 2), (_T2, 8)):
            self.a.process(
                make_record(ts, [make_cell(cell_metrics=make_cell_metrics(late_ul=late_ul), ue_list=[make_ue(1)])])
            )
        self.assertEqual(self.a.report().max_late_ul_harqs, 8)

    def test_max_late_dl_across_cells(self):
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(cell_metrics=make_cell_metrics(late_dl=10)),
                    make_cell(cell_metrics=make_cell_metrics(late_dl=20)),
                ],
            )
        )
        self.assertEqual(self.a.report().max_late_dl_harqs, 20)

    def test_max_late_ul_across_cells_and_records(self):
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(cell_metrics=make_cell_metrics(late_ul=3)),
                    make_cell(cell_metrics=make_cell_metrics(late_ul=7)),
                ],
            )
        )
        self.a.process(
            make_record(
                _T1,
                [
                    make_cell(cell_metrics=make_cell_metrics(late_ul=5)),
                ],
            )
        )
        self.assertEqual(self.a.report().max_late_ul_harqs, 7)


# ── TestGeneralMetricsAnalyzer — PUCCH invalid counts ────────────────────────


class TestGeneralMetricsAnalyzerPucch(unittest.TestCase):
    """
    PUCCH values are accumulated from the PREVIOUS record's ue_list,
    excluding any RNTI that had a ue_create/ue_reconf/ue_rem event recently.

    Exclusion window: an event in record N causes the RNTI to be excluded
    in records N and N+1 (i.e., two consecutive PUCCH accumulations are skipped).
    From record N+2 onwards the RNTI is included again.
    """

    def setUp(self):
        self.a = GeneralMetricsAnalyzer()

    def _process(self, ts, ue_specs, events=None):
        """Process one record. ue_specs = [(rnti, f0f1), ...]."""
        ue_list = [make_ue(rnti, pucch_f0f1=f0f1) for rnti, f0f1 in ue_specs]
        self.a.process(
            make_record(ts, [make_cell(cell_metrics=make_cell_metrics(), ue_list=ue_list, event_list=events or [])])
        )

    def test_first_record_not_accumulated(self):
        # No prev_ue_list yet → PUCCH cannot be counted.
        self._process(_T0, [(1, 10)])
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 0)

    def test_second_record_adds_prev_ue_list(self):
        self._process(_T0, [(1, 7)])
        self._process(_T1, [(1, 0)])
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 7)

    def test_multiple_ues_summed(self):
        self._process(_T0, [(1, 3), (2, 5)])
        self._process(_T1, [(1, 0), (2, 0)])
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 8)

    def test_accumulates_across_records(self):
        # Record 1 pucch=4, record 2 pucch=6, record 3 triggers accumulation of both.
        self._process(_T0, [(1, 4)])
        self._process(_T1, [(1, 6)])
        self._process(_T2, [(1, 0)])
        # Record 2 adds record1's value (4); record 3 adds record2's value (6).
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 10)

    def test_f2f3f4_harq_and_csi_fields(self):
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(
                        cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, pucch_f2f3f4_harq=3, pucch_f2f3f4_csi=7)]
                    )
                ],
            )
        )
        self.a.process(make_record(_T1, [make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1)])]))
        m = self.a.report()
        self.assertEqual(m.nof_pucch_f2f3f4_invalid_harqs, 3)
        self.assertEqual(m.nof_pucch_f2f3f4_invalid_csis, 7)

    def test_excluded_after_ue_create(self):
        # Event at record 2 → excluded at records 2 and 3 → included from record 4.
        self._process(_T0, [(1, 10)])
        self._process(_T1, [(1, 10)], events=[make_event(1, "ue_create")])
        self._process(_T2, [(1, 10)])
        self._process(_T3, [(1, 10)])
        # Record 4 adds record3's pucch=10; records 2 and 3 were excluded.
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 10)

    def test_excluded_after_ue_rem(self):
        self._process(_T0, [(1, 10)])
        self._process(_T1, [(1, 10)], events=[make_event(1, "ue_rem")])
        self._process(_T2, [(1, 10)])
        # After 3 records: rnti=1 still excluded at record 3 → total=0.
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 0)

    def test_excluded_for_exactly_two_reports_then_included(self):
        self._process(_T0, [(1, 10)])
        self._process(_T1, [(1, 10)], events=[make_event(1, "ue_create")])
        self._process(_T2, [(1, 10)])
        # Records 2 and 3: both excluded → still 0.
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 0)
        # Record 4: exclusion lifted → adds record3's pucch=10.
        self._process(_T3, [(1, 10)])
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 10)

    def test_unaffected_ue_counted_during_exclusion_window(self):
        # rnti=1 has an event; rnti=2 is unaffected → only rnti=2 is accumulated.
        self._process(_T0, [(1, 10), (2, 5)])
        self._process(_T1, [(1, 10), (2, 5)], events=[make_event(1, "ue_create")])
        self._process(_T2, [(1, 10), (2, 5)])
        # Records 2 and 3: rnti=1 excluded, rnti=2 included.
        # Record 2 adds rnti=2 pucch=5; record 3 adds rnti=2 pucch=5 → total=10.
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 10)

    def test_multiple_cells_pucch_summed(self):
        self.a.process(
            make_record(
                _T0,
                [
                    make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1, pucch_f0f1=3)]),
                    make_cell(ue_list=[make_ue(2, pucch_f0f1=5)]),
                ],
            )
        )
        self.a.process(
            make_record(
                _T1,
                [
                    make_cell(cell_metrics=make_cell_metrics(), ue_list=[make_ue(1)]),
                    make_cell(ue_list=[make_ue(2)]),
                ],
            )
        )
        self.assertEqual(self.a.report().nof_pucch_f0f1_invalid_harqs, 8)


# ── TestPerUePeakAverageAnalyzer ──────────────────────────────────────────────


class TestPerUePeakAverageAnalyzer(unittest.TestCase):
    """
    PerUePeakAverageAnalyzer tracks per-RNTI 5/15/30-sample peak moving averages.

    The 'peak' for each window is the maximum value that window's average has
    ever reached — it never decreases.
    """

    def setUp(self):
        self.a = PerUePeakAverageAnalyzer()

    def _process(self, cells):
        self.a.process(make_record(_T0, cells))

    def _ue(self, rnti):
        for ue in self.a.report().ue_array:
            if ue.rnti == rnti:
                return ue
        return None

    # Basic

    def test_empty_report(self):
        self.assertEqual(len(self.a.report().ue_array), 0)

    def test_single_ue_single_record(self):
        self._process([make_cell(ue_list=[make_ue(1, dl_brate=100.0, ul_brate=200.0)])])
        ue = self._ue(1)
        self.assertIsNotNone(ue)
        self.assertAlmostEqual(ue.dl_av_5_samples, 100.0)
        self.assertAlmostEqual(ue.dl_av_15_samples, 100.0)
        self.assertAlmostEqual(ue.dl_av_30_samples, 100.0)
        self.assertAlmostEqual(ue.ul_av_5_samples, 200.0)
        self.assertAlmostEqual(ue.ul_av_15_samples, 200.0)
        self.assertAlmostEqual(ue.ul_av_30_samples, 200.0)

    def test_peak_monotonically_increases(self):
        for dl in (100.0, 200.0, 50.0):
            self._process([make_cell(ue_list=[make_ue(1, dl_brate=dl)])])
        # Peak is the max 5-sample window average ever seen:
        #   record1: avg([100])=100; record2: avg([100,200])=150; record3: avg([100,200,50])=116.7
        # → peak5 = 150
        self.assertAlmostEqual(self._ue(1).dl_av_5_samples, 150.0)

    def test_peak_does_not_decrease(self):
        # High value followed by many low values.
        self._process([make_cell(ue_list=[make_ue(1, dl_brate=1000.0)])])
        for _ in range(10):
            self._process([make_cell(ue_list=[make_ue(1, dl_brate=1.0)])])
        self.assertAlmostEqual(self._ue(1).dl_av_5_samples, 1000.0)

    # Multiple UEs / cells

    def test_multiple_ues_tracked_separately(self):
        self._process([make_cell(ue_list=[make_ue(1, dl_brate=100.0), make_ue(2, dl_brate=200.0)])])
        self.assertAlmostEqual(self._ue(1).dl_av_5_samples, 100.0)
        self.assertAlmostEqual(self._ue(2).dl_av_5_samples, 200.0)

    def test_new_ue_joins_mid_stream(self):
        self._process([make_cell(ue_list=[make_ue(1, dl_brate=100.0)])])
        self._process([make_cell(ue_list=[make_ue(1, dl_brate=100.0), make_ue(2, dl_brate=50.0)])])
        ue2 = self._ue(2)
        self.assertIsNotNone(ue2)
        self.assertAlmostEqual(ue2.dl_av_5_samples, 50.0)

    def test_multiple_cells_different_ues_tracked_independently(self):
        self._process(
            [
                make_cell(ue_list=[make_ue(1, dl_brate=100.0)]),
                make_cell(ue_list=[make_ue(2, dl_brate=200.0)]),
            ]
        )
        self.assertAlmostEqual(self._ue(1).dl_av_5_samples, 100.0)
        self.assertAlmostEqual(self._ue(2).dl_av_5_samples, 200.0)

    def test_multiple_cells_same_rnti_accumulates_in_one_moving_average(self):
        # RNTI=1 appears in two cells: both brate samples go into the same queue.
        # After processing: queue = [100, 200], avg(2) = 150.
        self._process(
            [
                make_cell(ue_list=[make_ue(1, dl_brate=100.0)]),
                make_cell(ue_list=[make_ue(1, dl_brate=200.0)]),
            ]
        )
        self.assertAlmostEqual(self._ue(1).dl_av_5_samples, 150.0)

    def test_multiple_ues_multiple_cells_multiple_records(self):
        # 2 cells × 2 UEs each, 3 records with increasing rates.
        for i in range(1, 4):
            dl = float(i * 100)
            self._process(
                [
                    make_cell(ue_list=[make_ue(1, dl_brate=dl), make_ue(2, dl_brate=dl * 2)]),
                    make_cell(ue_list=[make_ue(3, dl_brate=dl * 3), make_ue(4, dl_brate=dl * 4)]),
                ]
            )
        # Peak is the max 5-sample window average across all records.
        # rnti=1: samples=[100,200,300] → peak5 = max(100, 150, 200) = 200
        # rnti=2: samples=[200,400,600] → peak5 = max(200, 300, 400) = 400
        # rnti=3: samples=[300,600,900] → peak5 = max(300, 450, 600) = 600
        # rnti=4: samples=[400,800,1200] → peak5 = max(400, 600, 800) = 800
        self.assertAlmostEqual(self._ue(1).dl_av_5_samples, 200.0)
        self.assertAlmostEqual(self._ue(2).dl_av_5_samples, 400.0)
        self.assertAlmostEqual(self._ue(3).dl_av_5_samples, 600.0)
        self.assertAlmostEqual(self._ue(4).dl_av_5_samples, 800.0)

    # Window sizes

    def test_windows_5_15_30_with_enough_samples(self):
        # 35 records with dl=1..35 (strictly increasing → peak is always at latest).
        for i in range(1, 36):
            self._process([make_cell(ue_list=[make_ue(1, dl_brate=float(i))])])
        ue = self._ue(1)
        # Queue = [1..35] (maxlen=50, all fit).
        # avg(last 5)  = avg(31..35) = 33.0
        # avg(last 15) = avg(21..35) = 28.0
        # avg(last 30) = avg(6..35)  = 20.5
        self.assertAlmostEqual(ue.dl_av_5_samples, 33.0)
        self.assertAlmostEqual(ue.dl_av_15_samples, 28.0)
        self.assertAlmostEqual(ue.dl_av_30_samples, 20.5)

    def test_window_with_fewer_samples_than_k_uses_all_available(self):
        for dl in (10.0, 20.0, 30.0):
            self._process([make_cell(ue_list=[make_ue(1, dl_brate=dl)])])
        ue = self._ue(1)
        # Only 3 samples; all window sizes fall back to avg(10,20,30) = 20.0.
        self.assertAlmostEqual(ue.dl_av_5_samples, 20.0)
        self.assertAlmostEqual(ue.dl_av_15_samples, 20.0)
        self.assertAlmostEqual(ue.dl_av_30_samples, 20.0)

    def test_ul_peak_tracked_independently_from_dl(self):
        # DL increases, UL decreases.
        for dl, ul in ((100.0, 300.0), (200.0, 200.0), (300.0, 100.0)):
            self._process([make_cell(ue_list=[make_ue(1, dl_brate=dl, ul_brate=ul)])])
        ue = self._ue(1)
        # DL queue=[100,200,300]: peak5 = max(100, 150, 200) = 200
        self.assertAlmostEqual(ue.dl_av_5_samples, 200.0)
        # UL queue=[300,200,100]: peak5 = max(300, 250, 200) = 300
        self.assertAlmostEqual(ue.ul_av_5_samples, 300.0)


if __name__ == "__main__":
    unittest.main()
