# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
JSON metrics analyzer for the CU-CP counters of the gNB.
"""

from typing import Dict

from retina.protocol.base_pb2 import CuCpMetrics, Metrics

from retina.agent.features.json_metrics.analyzer import JsonMetricsAnalyzer


class CuCpMetricsAnalyzer(JsonMetricsAnalyzer):
    """
    Tracks the RRC connection establishments with cause mt-Access, i.e. the paged UEs that connected.

    The CU-CP counters are cumulative, so the last report of each DU holds its total.
    """

    def __init__(self) -> None:
        self._nof_mt_access_per_du: Dict[int, int] = {}

    def process(self, metric_info: dict) -> None:
        for du_info in metric_info.get("cu-cp", {}).get("rrcs", {}).get("du", []):
            successful = du_info.get("rrc_connection_establishment", {}).get(
                "successful_rrc_connection_establishments", {}
            )
            self._nof_mt_access_per_du[du_info["gnb_du_id"]] = successful.get("mt_access", 0)

    def report(self) -> Metrics:
        return Metrics(
            cu_cp=CuCpMetrics(nof_mt_access_rrc_connection_establishments=sum(self._nof_mt_access_per_du.values()))
        )
