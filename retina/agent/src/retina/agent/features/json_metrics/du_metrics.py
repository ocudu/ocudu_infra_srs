# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
JSON metrics analyzer for the DU: per-UE metrics and aggregate counters.
"""

import datetime
from typing import Dict, List, Optional, Tuple

from retina.protocol.base_pb2 import Metrics, UeMetrics

from retina.agent.features.json_metrics.analyzer import JsonMetricsAnalyzer, MovingAverage


class DuMetricsAnalyzer(JsonMetricsAnalyzer):  # pylint: disable=too-many-instance-attributes
    """
    Computes per-UE and aggregate DU metrics from JSON WebSocket records.

    Per-RNTI: 50-sample moving averages, peak windows (5/15/30), time-weighted
    bitrate/RI, cumulative KOs and PUCCH (with event-based exclusion).

    Aggregate bitrate/RI: time-weighted average of the per-record total, preserving
    correct multi-UE semantics.  KOs and PUCCH are derived from per-RNTI sums at
    report() time.
    """

    def __init__(self) -> None:
        # Per-RNTI state
        self._dl_mov_av: Dict[int, MovingAverage] = {}
        self._ul_mov_av: Dict[int, MovingAverage] = {}
        self._dl_peak: Dict[int, Tuple[float, float, float]] = {}
        self._ul_peak: Dict[int, Tuple[float, float, float]] = {}
        self._time_first: Dict[int, Optional[datetime.datetime]] = {}
        self._time_last: Dict[int, Optional[datetime.datetime]] = {}
        self._dl_bitrate: Dict[int, float] = {}
        self._ul_bitrate: Dict[int, float] = {}
        self._dl_avg_ri: Dict[int, float] = {}
        self._ul_avg_ri: Dict[int, float] = {}
        self._dl_max_mcs: Dict[int, int] = {}
        self._ul_max_mcs: Dict[int, int] = {}
        self._nof_ko_dl: Dict[int, int] = {}
        self._nof_ko_ul: Dict[int, int] = {}
        self._pucch_f0f1: Dict[int, int] = {}
        self._pucch_f2f3f4_harqs: Dict[int, int] = {}
        self._pucch_f2f3f4_csis: Dict[int, int] = {}
        self._pusch_csis: Dict[int, int] = {}
        self._pusch_harqs: Dict[int, int] = {}
        self._pci: Dict[int, int] = {}

        # Aggregate time-weighted bitrate/RI (time-weighted average of per-record sum)
        self._agg_time_first: Optional[datetime.datetime] = None
        self._agg_time_last: Optional[datetime.datetime] = None
        self._agg_dl_bitrate: float = 0.0
        self._agg_ul_bitrate: float = 0.0
        self._agg_dl_ri: float = 0.0
        self._agg_ul_ri: float = 0.0

        # PUCCH event exclusion (shared, called once per cell)
        self._reports_since_last_ue_event: Dict[int, int] = {}
        self._prev_ue_list: List[Dict] = []

    def _init_rnti(self, rnti: int, pci: int) -> None:
        if rnti not in self._dl_mov_av:
            self._dl_mov_av[rnti] = MovingAverage(50)
            self._ul_mov_av[rnti] = MovingAverage(50)
            self._dl_peak[rnti] = (0.0, 0.0, 0.0)
            self._ul_peak[rnti] = (0.0, 0.0, 0.0)
            self._time_first[rnti] = None
            self._time_last[rnti] = None
            self._dl_bitrate[rnti] = 0.0
            self._ul_bitrate[rnti] = 0.0
            self._dl_avg_ri[rnti] = 0.0
            self._ul_avg_ri[rnti] = 0.0
            self._dl_max_mcs[rnti] = 0
            self._ul_max_mcs[rnti] = 0
            self._nof_ko_dl[rnti] = 0
            self._nof_ko_ul[rnti] = 0
            self._pucch_f0f1[rnti] = 0
            self._pucch_f2f3f4_harqs[rnti] = 0
            self._pucch_f2f3f4_csis[rnti] = 0
            self._pusch_csis[rnti] = 0
            self._pusch_harqs[rnti] = 0
            self._pci[rnti] = pci

    def _handle_events(self, cell_info: dict) -> None:
        for rnti in list(self._reports_since_last_ue_event):
            self._reports_since_last_ue_event[rnti] += 1
            if self._reports_since_last_ue_event[rnti] > 1:
                self._reports_since_last_ue_event.pop(rnti)
        for event in cell_info.get("event_list", []):
            if event["event_type"] in ("ue_create", "ue_reconf", "ue_rem"):
                self._reports_since_last_ue_event[event["rnti"]] = 0

    def _update_rnti_time_weighted(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        rnti: int,
        timestamp: datetime.datetime,
        dl_brate: float,
        ul_brate: float,
        dl_ri: Optional[float],
        ul_ri: Optional[float],
    ) -> None:
        if self._time_first[rnti] is None:
            self._time_first[rnti] = timestamp
            self._time_last[rnti] = timestamp
            self._dl_bitrate[rnti] = dl_brate
            self._ul_bitrate[rnti] = ul_brate
            if dl_ri is not None:
                self._dl_avg_ri[rnti] = dl_ri
            if ul_ri is not None:
                self._ul_avg_ri[rnti] = ul_ri
            return

        t_old = (self._time_last[rnti] - self._time_first[rnti]).total_seconds()  # type: ignore[operator]
        t_new = (timestamp - self._time_last[rnti]).total_seconds()  # type: ignore[operator]
        t_beginning = (timestamp - self._time_first[rnti]).total_seconds()  # type: ignore[operator]

        if t_beginning > 0:
            self._dl_bitrate[rnti] = ((self._dl_bitrate[rnti] * t_old) + (dl_brate * t_new)) / t_beginning
            self._ul_bitrate[rnti] = ((self._ul_bitrate[rnti] * t_old) + (ul_brate * t_new)) / t_beginning
            if dl_ri is not None:
                self._dl_avg_ri[rnti] = ((self._dl_avg_ri[rnti] * t_old) + (dl_ri * t_new)) / t_beginning
            if ul_ri is not None:
                self._ul_avg_ri[rnti] = ((self._ul_avg_ri[rnti] * t_old) + (ul_ri * t_new)) / t_beginning

        self._time_last[rnti] = timestamp

    def _update_agg_bitrate(self, timestamp: datetime.datetime, dl_brate: float, ul_brate: float) -> None:
        if self._agg_time_first is None or self._agg_time_last is None:
            return
        t_old = (self._agg_time_last - self._agg_time_first).total_seconds()
        t_new = (timestamp - self._agg_time_last).total_seconds()
        t_beginning = (timestamp - self._agg_time_first).total_seconds()
        if t_beginning == 0:
            self._agg_dl_bitrate = dl_brate
            self._agg_ul_bitrate = ul_brate
        else:
            self._agg_dl_bitrate = ((self._agg_dl_bitrate * t_old) + (dl_brate * t_new)) / t_beginning
            self._agg_ul_bitrate = ((self._agg_ul_bitrate * t_old) + (ul_brate * t_new)) / t_beginning

    def _update_agg_ri(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        timestamp: datetime.datetime,
        total_dl_ri: float,
        dl_count: int,
        total_ul_ri: float,
        ul_count: int,
    ) -> None:
        if self._agg_time_first is None or self._agg_time_last is None:
            return
        t_old = (self._agg_time_last - self._agg_time_first).total_seconds()
        t_new = (timestamp - self._agg_time_last).total_seconds()
        t_beginning = (timestamp - self._agg_time_first).total_seconds()
        if dl_count > 0:
            sample_dl_ri = total_dl_ri / dl_count
            if t_beginning == 0:
                self._agg_dl_ri = sample_dl_ri
            else:
                self._agg_dl_ri = ((self._agg_dl_ri * t_old) + (sample_dl_ri * t_new)) / t_beginning
        if ul_count > 0:
            sample_ul_ri = total_ul_ri / ul_count
            if t_beginning == 0:
                self._agg_ul_ri = sample_ul_ri
            else:
                self._agg_ul_ri = ((self._agg_ul_ri * t_old) + (sample_ul_ri * t_new)) / t_beginning

    def process(self, metric_info: dict) -> None:  # pylint: disable=too-many-locals,too-many-statements
        if "cells" not in metric_info:
            return

        timestamp = (
            datetime.datetime.fromisoformat(metric_info["timestamp"].strip()) if "timestamp" in metric_info else None
        )

        total_dl_brate = 0.0
        total_ul_brate = 0.0
        total_dl_ri = 0.0
        total_dl_ri_count = 0
        total_ul_ri = 0.0
        total_ul_ri_count = 0

        for cell_info in metric_info["cells"]:
            pci = cell_info.get("cell_metrics", {}).get("pci", 0) if cell_info.get("cell_metrics") else 0
            self._handle_events(cell_info)

            for ue_info in self._prev_ue_list:
                rnti = ue_info["rnti"]
                if rnti not in self._reports_since_last_ue_event:
                    self._pucch_f0f1[rnti] = self._pucch_f0f1.get(rnti, 0) + ue_info["nof_pucch_f0f1_invalid_harqs"]
                    self._pucch_f2f3f4_harqs[rnti] = (
                        self._pucch_f2f3f4_harqs.get(rnti, 0) + ue_info["nof_pucch_f2f3f4_invalid_harqs"]
                    )
                    self._pucch_f2f3f4_csis[rnti] = (
                        self._pucch_f2f3f4_csis.get(rnti, 0) + ue_info["nof_pucch_f2f3f4_invalid_csis"]
                    )
                    self._pusch_csis[rnti] = self._pusch_csis.get(rnti, 0) + ue_info.get("nof_pusch_invalid_csis", 0)
                    self._pusch_harqs[rnti] = self._pusch_harqs.get(rnti, 0) + ue_info.get("nof_pusch_invalid_harqs", 0)

            ue_list = cell_info.get("ue_list", [])

            if ue_list and self._agg_time_first is None and timestamp is not None:
                if self._agg_time_last is None:
                    self._agg_time_last = timestamp
                self._agg_time_first = self._agg_time_last

            for ue_info in ue_list:
                rnti = ue_info["rnti"]
                self._init_rnti(rnti, pci)

                self._dl_mov_av[rnti].add(ue_info["dl_brate"])
                self._ul_mov_av[rnti].add(ue_info["ul_brate"])
                dl5 = self._dl_mov_av[rnti].get_average(5)
                dl15 = self._dl_mov_av[rnti].get_average(15)
                dl30 = self._dl_mov_av[rnti].get_average(30)
                ul5 = self._ul_mov_av[rnti].get_average(5)
                ul15 = self._ul_mov_av[rnti].get_average(15)
                ul30 = self._ul_mov_av[rnti].get_average(30)
                old_dl = self._dl_peak[rnti]
                old_ul = self._ul_peak[rnti]
                self._dl_peak[rnti] = (max(old_dl[0], dl5), max(old_dl[1], dl15), max(old_dl[2], dl30))
                self._ul_peak[rnti] = (max(old_ul[0], ul5), max(old_ul[1], ul15), max(old_ul[2], ul30))

                self._nof_ko_dl[rnti] += ue_info["dl_nof_nok"]
                self._nof_ko_ul[rnti] += ue_info["ul_nof_nok"]
                self._dl_max_mcs[rnti] = max(self._dl_max_mcs[rnti], ue_info.get("dl_mcs", 0))
                self._ul_max_mcs[rnti] = max(self._ul_max_mcs[rnti], ue_info.get("ul_mcs", 0))

                if timestamp is not None:
                    self._update_rnti_time_weighted(
                        rnti,
                        timestamp,
                        ue_info["dl_brate"],
                        ue_info["ul_brate"],
                        ue_info.get("dl_ri"),
                        ue_info.get("ul_ri"),
                    )

                total_dl_brate += ue_info["dl_brate"]
                total_ul_brate += ue_info["ul_brate"]
                total_dl_ri += ue_info.get("dl_ri", 0.0)
                total_ul_ri += ue_info.get("ul_ri", 0.0)
                if "dl_ri" in ue_info:
                    total_dl_ri_count += 1
                if "ul_ri" in ue_info:
                    total_ul_ri_count += 1

            self._prev_ue_list = ue_list

        if timestamp is not None:
            self._update_agg_bitrate(timestamp, total_dl_brate, total_ul_brate)
            self._update_agg_ri(timestamp, total_dl_ri, total_dl_ri_count, total_ul_ri, total_ul_ri_count)
            self._agg_time_last = timestamp

    def report(self) -> Metrics:
        metrics = Metrics()
        for rnti in self._dl_peak:  # pylint: disable=consider-using-dict-items,consider-using-dict-items
            dl5, dl15, dl30 = self._dl_peak[rnti]
            ul5, ul15, ul30 = self._ul_peak[rnti]
            dl_mid10 = self._dl_mov_av[rnti].get_middle_average(10)
            ul_mid10 = self._ul_mov_av[rnti].get_middle_average(10)
            metrics.ue_array.append(
                UeMetrics(
                    rnti=rnti,
                    pci=self._pci.get(rnti, 0),
                    dl_bitrate=self._dl_bitrate.get(rnti, 0.0),
                    ul_bitrate=self._ul_bitrate.get(rnti, 0.0),
                    dl_av_5_samples=dl5,
                    dl_av_15_samples=dl15,
                    dl_av_30_samples=dl30,
                    ul_av_5_samples=ul5,
                    ul_av_15_samples=ul15,
                    ul_av_30_samples=ul30,
                    dl_av_mid10_samples=dl_mid10,
                    ul_av_mid10_samples=ul_mid10,
                    nof_ko_dl=self._nof_ko_dl.get(rnti, 0),
                    nof_ko_ul=self._nof_ko_ul.get(rnti, 0),
                    nof_pucch_f0f1_invalid_harqs=self._pucch_f0f1.get(rnti, 0),
                    nof_pucch_f2f3f4_invalid_harqs=self._pucch_f2f3f4_harqs.get(rnti, 0),
                    nof_pucch_f2f3f4_invalid_csis=self._pucch_f2f3f4_csis.get(rnti, 0),
                    nof_pusch_invalid_csis=self._pusch_csis.get(rnti, 0),
                    nof_pusch_invalid_harqs=self._pusch_harqs.get(rnti, 0),
                    dl_avg_ri=self._dl_avg_ri.get(rnti, 0.0),
                    ul_avg_ri=self._ul_avg_ri.get(rnti, 0.0),
                    dl_max_mcs=self._dl_max_mcs.get(rnti, 0),
                    ul_max_mcs=self._ul_max_mcs.get(rnti, 0),
                )
            )
        metrics.aggregate.nof_ko_dl = sum(self._nof_ko_dl.values())
        metrics.aggregate.nof_ko_ul = sum(self._nof_ko_ul.values())
        metrics.aggregate.nof_pucch_f0f1_invalid_harqs = sum(self._pucch_f0f1.values())
        metrics.aggregate.nof_pucch_f2f3f4_invalid_harqs = sum(self._pucch_f2f3f4_harqs.values())
        metrics.aggregate.nof_pucch_f2f3f4_invalid_csis = sum(self._pucch_f2f3f4_csis.values())
        metrics.aggregate.nof_pusch_invalid_csis = sum(self._pusch_csis.values())
        metrics.aggregate.nof_pusch_invalid_harqs = sum(self._pusch_harqs.values())
        metrics.aggregate.dl_bitrate = self._agg_dl_bitrate
        metrics.aggregate.ul_bitrate = self._agg_ul_bitrate
        metrics.aggregate.dl_avg_ri = self._agg_dl_ri
        metrics.aggregate.ul_avg_ri = self._agg_ul_ri
        metrics.aggregate.dl_max_mcs = max(self._dl_max_mcs.values(), default=0)
        metrics.aggregate.ul_max_mcs = max(self._ul_max_mcs.values(), default=0)
        return metrics
