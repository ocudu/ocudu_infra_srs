# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
JSON metrics analyzer for the Amarisoft UE.
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Set, Tuple

from retina.protocol.base_pb2 import Metrics, UeMetrics

from retina.agent.features.json_metrics.analyzer import JsonMetricsAnalyzer


class AmarisoftUeMetricsAnalyzer(JsonMetricsAnalyzer):
    """
    Accumulates per-UE and aggregate metrics for Amarisoft UE subscribers.

    Keyed by (rnti, pci). Peer-to-UE mapping and subscriber filtering are the
    caller's responsibility — this class is agnostic of gRPC context and subscribers.

    ue_get responses feed per-UE data via process(); stats responses feed the
    aggregate UeMetrics and per-cell counters via process_stats().
    """

    def __init__(self) -> None:
        self._ue_metrics: Dict[Tuple[int, int], UeMetrics] = {}  # (rnti, pci) -> UeMetrics
        self._ue_time: Dict[Tuple[int, int], Tuple[datetime, datetime]] = {}
        self._stats_ue_metrics: Optional[UeMetrics] = None
        self._nof_pdu_session_accept: int = 0

    def process(self, metric_info: dict) -> None:
        if not metric_info:
            return None
        if "ue_list" in metric_info:
            return self._process_ue(metric_info)
        return self._process_stats(metric_info)

    def _process_ue(self, metric_info: dict) -> None:
        timestamp = datetime.fromtimestamp(metric_info["utc"], tz=timezone.utc)
        for ue_info in metric_info.get("ue_list", []):
            rnti = ue_info.get("rnti", 0)
            for cell_info in ue_info.get("cells", []):
                pci = cell_info["pci"]
                ue_id = (rnti, pci)
                if ue_id not in self._ue_metrics:
                    self._ue_metrics[ue_id] = UeMetrics(
                        rnti=rnti,
                        pci=pci,
                        nof_ko_dl=ue_info["dl_err_count"] + ue_info["dl_retx_count"],
                        dl_bitrate=ue_info["dl_bitrate"],
                        nof_ko_ul=ue_info["ul_retx_count"],
                        ul_bitrate=ue_info["ul_bitrate"],
                        dl_max_mcs=int(ue_info.get("dl_mcs", 0)),
                        ul_max_mcs=int(ue_info.get("ul_mcs", 0)),
                    )
                    self._ue_time[ue_id] = (timestamp, timestamp)
                else:
                    ue_m = self._ue_metrics[ue_id]
                    time_first, time_last = self._ue_time[ue_id]

                    ue_m.nof_ko_dl += ue_info["dl_err_count"] + ue_info["dl_retx_count"]
                    ue_m.nof_ko_ul += ue_info["ul_retx_count"]
                    ue_m.dl_max_mcs = max(ue_m.dl_max_mcs, int(ue_info.get("dl_mcs", 0)))
                    ue_m.ul_max_mcs = max(ue_m.ul_max_mcs, int(ue_info.get("ul_mcs", 0)))

                    t_old = (time_last - time_first).total_seconds()
                    t_new = (timestamp - time_last).total_seconds()
                    t_beginning = (timestamp - time_first).total_seconds()

                    if t_beginning:
                        ue_m.dl_bitrate = ((ue_m.dl_bitrate * t_old) + (ue_info["dl_bitrate"] * t_new)) / t_beginning
                        ue_m.ul_bitrate = ((ue_m.ul_bitrate * t_old) + (ue_info["ul_bitrate"] * t_new)) / t_beginning

                    self._ue_time[ue_id] = (time_first, timestamp)

    def _process_stats(self, stats_dict: dict) -> None:
        if self._stats_ue_metrics is None:
            self._stats_ue_metrics = UeMetrics()
        cells = stats_dict["cells"].values()

        # Rates are instantaneous (per sampling window): keep the latest sample.
        self._stats_ue_metrics.dl_bitrate = sum(cell["dl_bitrate"] for cell in cells)
        self._stats_ue_metrics.ul_bitrate = sum(cell["ul_bitrate"] for cell in cells)

        # Reset-on-query counters: accumulate across the periodic "stats" calls.
        self._stats_ue_metrics.nof_ko_dl += sum(cell["dl_err_count"] + cell["dl_retx_count"] for cell in cells)
        self._stats_ue_metrics.nof_ko_ul += sum(cell["ul_retx_count"] for cell in cells)

        # Message counters (counters.messages) are cumulative, not reset by "stats": latest wins.
        self._stats_ue_metrics.nof_handovers = stats_dict["counters"]["messages"].get("handover_success", 0)
        self._nof_pdu_session_accept = stats_dict["counters"]["messages"].get(
            "5gs_nas_pdu_session_establishment_accept", 0
        )

    def latest_ue_id(self, ue_ids: Set[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        """Return the (rnti, pci) most recently updated among ue_ids, or None."""
        candidates = [(uid, self._ue_time[uid][1]) for uid in ue_ids if uid in self._ue_time]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[1])[0]

    def report(self, ue_ids: Optional[Set[Tuple[int, int]]] = None) -> Metrics:
        """
        Build a Metrics object.

        ue_ids=None: include all UEs; aggregate comes from stats when available.
        ue_ids=set: include only those UEs; aggregate is summed from their data.
        """
        metrics = Metrics()
        metrics.core.nof_pdu_session_establishment_accept = self._nof_pdu_session_accept

        selected = (
            [self._ue_metrics[uid] for uid in ue_ids if uid in self._ue_metrics]
            if ue_ids is not None
            else list(self._ue_metrics.values())
        )

        for ue_m in selected:
            metrics.ue_array.append(ue_m)
            metrics.aggregate.dl_bitrate += ue_m.dl_bitrate
            metrics.aggregate.ul_bitrate += ue_m.ul_bitrate
            metrics.aggregate.nof_ko_dl += ue_m.nof_ko_dl
            metrics.aggregate.nof_ko_ul += ue_m.nof_ko_ul
            metrics.aggregate.nof_handovers += ue_m.nof_handovers

        metrics.aggregate.dl_max_mcs = max((ue_m.dl_max_mcs for ue_m in selected), default=0)
        metrics.aggregate.ul_max_mcs = max((ue_m.ul_max_mcs for ue_m in selected), default=0)

        if ue_ids is None and self._stats_ue_metrics is not None:
            metrics.aggregate.MergeFrom(self._stats_ue_metrics)

        return metrics
