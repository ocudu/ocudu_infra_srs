#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
JSON metrics analyzer for the DU.
"""

import datetime
from typing import Dict, List, Optional

from retina.protocol.base_pb2 import Metrics

from retina.agent.features.json_metrics.analyzer import JsonMetricsAnalyzer


class GeneralMetricsAnalyzer(JsonMetricsAnalyzer):
    """
    Computes aggregate DU metrics from JSON WebSocket records.
    """

    def __init__(self) -> None:
        self._metrics = Metrics()
        self._first_cell_report = True
        self._time_first: Optional[datetime.datetime] = None
        self._time_last: Optional[datetime.datetime] = None
        self._prev_ue_list: List[Dict] = []
        self._reports_since_last_ue_event: Dict[int, int] = {}

    def process(self, metric_info: dict) -> None:
        timestamp = datetime.datetime.fromisoformat(metric_info["timestamp"].strip())

        total_dl_brate = 0.0
        total_ul_brate = 0.0
        has_ue_list = False

        for cell_info in metric_info.get("cells", []):
            if "cell_metrics" in cell_info and cell_info["cell_metrics"]:
                if self._first_cell_report:
                    self._first_cell_report = False
                    if self._time_first is None:
                        self._time_first = timestamp
                        self._time_last = timestamp
                else:
                    self._metrics.nof_error_indications += cell_info["cell_metrics"]["error_indication_count"]

                self._metrics.max_late_dl_harqs = max(
                    self._metrics.max_late_dl_harqs, cell_info["cell_metrics"]["late_dl_harqs"]
                )
                self._metrics.max_late_ul_harqs = max(
                    self._metrics.max_late_ul_harqs, cell_info["cell_metrics"]["late_ul_harqs"]
                )

            if "ue_list" in cell_info:
                has_ue_list = True
                if self._time_first is None:
                    if not cell_info["ue_list"]:
                        continue
                    self._time_first = timestamp
                    self._time_last = timestamp

                self._handle_events(cell_info)

                self._metrics.nof_ko_dl += sum(u["dl_nof_nok"] for u in cell_info["ue_list"])
                self._metrics.nof_ko_ul += sum(u["ul_nof_nok"] for u in cell_info["ue_list"])
                total_dl_brate += sum(u["dl_brate"] for u in cell_info["ue_list"])
                total_ul_brate += sum(u["ul_brate"] for u in cell_info["ue_list"])

                # PUCCH from the previous report, excluding UEs with recent events
                for ue_info in self._prev_ue_list:
                    if ue_info["rnti"] not in self._reports_since_last_ue_event:
                        self._metrics.nof_pucch_f0f1_invalid_harqs += ue_info["nof_pucch_f0f1_invalid_harqs"]
                        self._metrics.nof_pucch_f2f3f4_invalid_harqs += ue_info["nof_pucch_f2f3f4_invalid_harqs"]
                        self._metrics.nof_pucch_f2f3f4_invalid_csis += ue_info["nof_pucch_f2f3f4_invalid_csis"]

                self._prev_ue_list = cell_info["ue_list"]

        if has_ue_list:
            self._update_bitrate(timestamp, total_dl_brate, total_ul_brate)

    def _handle_events(self, cell_info: dict) -> None:
        for rnti in list(self._reports_since_last_ue_event):
            self._reports_since_last_ue_event[rnti] += 1
            if self._reports_since_last_ue_event[rnti] > 1:
                del self._reports_since_last_ue_event[rnti]

        for event in cell_info.get("event_list", []):
            if event["event_type"] in ("ue_create", "ue_reconf", "ue_rem"):
                self._reports_since_last_ue_event[event["rnti"]] = 0

    def _update_bitrate(self, timestamp: datetime.datetime, dl_brate: float, ul_brate: float) -> None:
        if self._time_first is None or self._time_last is None:
            return
        t_old = (self._time_last - self._time_first).total_seconds()
        t_new = (timestamp - self._time_last).total_seconds()
        t_beginning = (timestamp - self._time_first).total_seconds()

        if t_beginning == 0:
            self._metrics.dl_bitrate = dl_brate
            self._metrics.ul_bitrate = ul_brate
        else:
            self._metrics.dl_bitrate = ((self._metrics.dl_bitrate * t_old) + (dl_brate * t_new)) / t_beginning
            self._metrics.ul_bitrate = ((self._metrics.ul_bitrate * t_old) + (ul_brate * t_new)) / t_beginning

        self._time_last = timestamp

    def report(self) -> Metrics:
        return self._metrics
