# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
JSON metrics analyzer for DU cell-level counters (error indications, late HARQs).
"""

from typing import List

from retina.protocol.base_pb2 import DuMetrics, Metrics

from retina.agent.features.json_metrics.analyzer import JsonMetricsAnalyzer, MovingAverage

_NOF_AVERAGE_SAMPLES = 50


class DuCellAnalyzer(JsonMetricsAnalyzer):  # pylint: disable=too-many-instance-attributes
    """
    Tracks cell-level DU metrics from the cell_metrics block of each JSON record.

    The first cell_metrics report is skipped to discard a spurious error indication
    the DU emits at startup.
    """

    def __init__(self) -> None:
        self._first_cell_report = True
        self._nof_error_indications: int = 0
        self._nof_conres_issues: int = 0
        self._total_prach_preambles: int = 0
        self._two_step_prachs_detected: int = 0
        self._max_late_dl_harqs: int = 0
        self._max_late_ul_harqs: int = 0
        self._pdsch_prbs_mov_av: List[MovingAverage] = []
        self._pusch_prbs_mov_av: List[MovingAverage] = []

    def process(self, metric_info: dict) -> None:
        for cell_info in metric_info.get("cells", []):
            cm = cell_info.get("cell_metrics")
            if not cm:
                continue
            # Counted from the first report onwards, a RA may happen before the startup report is discarded.
            self._total_prach_preambles += cm.get("total_prach_preambles", 0)
            self._two_step_prachs_detected += cm.get("two_step_prachs_detected", 0)
            if self._first_cell_report:
                self._first_cell_report = False
                continue
            self._nof_error_indications += cm["error_indication_count"]
            # A contention resolution that expires before the CE is sent or that is never acked
            # leaves the UE unscheduled, so both count as the same failure
            self._nof_conres_issues += cm.get("nof_conres_timer_expired", 0) + cm.get("nof_conres_ce_never_acked", 0)
            self._max_late_dl_harqs = max(self._max_late_dl_harqs, cm["late_dl_harqs"])
            self._max_late_ul_harqs = max(self._max_late_ul_harqs, cm["late_ul_harqs"])
            if "pdsch_prbs_used_per_tdd_slot_idx" in cm:
                values = cm["pdsch_prbs_used_per_tdd_slot_idx"]
                if not self._pdsch_prbs_mov_av:
                    self._pdsch_prbs_mov_av = [MovingAverage(_NOF_AVERAGE_SAMPLES) for _ in values]
                for ma, v in zip(self._pdsch_prbs_mov_av, values):
                    ma.add(v)
            if "pusch_prbs_used_per_tdd_slot_idx" in cm:
                values = cm["pusch_prbs_used_per_tdd_slot_idx"]
                if not self._pusch_prbs_mov_av:
                    self._pusch_prbs_mov_av = [MovingAverage(_NOF_AVERAGE_SAMPLES) for _ in values]
                for ma, v in zip(self._pusch_prbs_mov_av, values):
                    ma.add(v)

    def report(self) -> Metrics:
        return Metrics(
            du=DuMetrics(
                nof_error_indications=self._nof_error_indications,
                nof_conres_issues=self._nof_conres_issues,
                total_prach_preambles=self._total_prach_preambles,
                two_step_prachs_detected=self._two_step_prachs_detected,
                max_late_dl_harqs=self._max_late_dl_harqs,
                max_late_ul_harqs=self._max_late_ul_harqs,
                pdsch_prbs_used_per_tdd_slot_idx=[round(ma.get_average()) for ma in self._pdsch_prbs_mov_av],
                pusch_prbs_used_per_tdd_slot_idx=[round(ma.get_average()) for ma in self._pusch_prbs_mov_av],
                pdsch_prbs_mid10_per_tdd_slot_idx=[round(ma.get_middle_average(10)) for ma in self._pdsch_prbs_mov_av],
                pusch_prbs_mid10_per_tdd_slot_idx=[round(ma.get_middle_average(10)) for ma in self._pusch_prbs_mov_av],
            )
        )
