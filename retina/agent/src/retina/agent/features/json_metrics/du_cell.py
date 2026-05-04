# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
JSON metrics analyzer for DU cell-level counters (error indications, late HARQs).
"""

from retina.protocol.base_pb2 import DuMetrics, Metrics

from retina.agent.features.json_metrics.analyzer import JsonMetricsAnalyzer


class DuCellAnalyzer(JsonMetricsAnalyzer):
    """
    Tracks cell-level DU metrics from the cell_metrics block of each JSON record.

    The first cell_metrics report is skipped to discard a spurious error indication
    the DU emits at startup.
    """

    def __init__(self) -> None:
        self._first_cell_report = True
        self._nof_error_indications: int = 0
        self._max_late_dl_harqs: int = 0
        self._max_late_ul_harqs: int = 0

    def process(self, metric_info: dict) -> None:
        for cell_info in metric_info.get("cells", []):
            cm = cell_info.get("cell_metrics")
            if not cm:
                continue
            if self._first_cell_report:
                self._first_cell_report = False
                continue
            self._nof_error_indications += cm["error_indication_count"]
            self._max_late_dl_harqs = max(self._max_late_dl_harqs, cm["late_dl_harqs"])
            self._max_late_ul_harqs = max(self._max_late_ul_harqs, cm["late_ul_harqs"])

    def report(self) -> Metrics:
        return Metrics(
            du=DuMetrics(
                nof_error_indications=self._nof_error_indications,
                max_late_dl_harqs=self._max_late_dl_harqs,
                max_late_ul_harqs=self._max_late_ul_harqs,
            )
        )
