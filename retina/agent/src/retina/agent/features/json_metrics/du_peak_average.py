#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
JSON metrics analyzers for the DU: Per UE Peak Average.
"""

from collections import deque
from typing import Deque, Dict, Tuple

from retina.protocol.base_pb2 import Metrics, UeMetrics

from retina.agent.features.json_metrics.analyzer import JsonMetricsAnalyzer


class _MovingAverage:
    """Moving average queue for up to N samples."""

    def __init__(self, max_length):
        self._queue: Deque[float] = deque(maxlen=max_length)

    def add(self, value: float) -> None:
        """
        Add a new element to the queue
        """
        self._queue.append(value)

    def get_average(self, nof_average_samples=None) -> float:
        """
        Return the average of the last K elements in the queue
        """
        if nof_average_samples is None:
            nof_average_samples = self._queue.maxlen
        elif nof_average_samples > self._queue.maxlen or nof_average_samples < 0:
            raise ValueError("nof_average_samples is greater than the maximum length of the queue")
        if len(self._queue) == 0:
            return 0
        last_k_values = list(self._queue)[-nof_average_samples:]
        return sum(last_k_values) / len(last_k_values)


class PerUePeakAverageAnalyzer(JsonMetricsAnalyzer):
    """
    Computes per-UE peak moving-average DL/UL bitrates from JSON WebSocket records.

    Tracks a 50-sample moving average per RNTI and records the peak (max) value
    observed over windows of 5, 15, and 30 samples.
    """

    def __init__(self) -> None:
        self._dl_mov_av: Dict[int, _MovingAverage] = {}
        self._ul_mov_av: Dict[int, _MovingAverage] = {}
        self._dl_peak: Dict[int, Tuple[float, float, float]] = {}
        self._ul_peak: Dict[int, Tuple[float, float, float]] = {}

    def process(self, metric_info: dict) -> None:
        for cell_info in metric_info.get("cells", []):
            for ue_info in cell_info.get("ue_list", []):
                rnti = ue_info["rnti"]

                if rnti not in self._dl_mov_av:
                    self._dl_mov_av[rnti] = _MovingAverage(50)
                    self._ul_mov_av[rnti] = _MovingAverage(50)
                    self._dl_peak[rnti] = (0.0, 0.0, 0.0)
                    self._ul_peak[rnti] = (0.0, 0.0, 0.0)

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

    def report(self) -> Metrics:
        metrics = Metrics()
        for rnti in self._dl_peak:  # pylint: disable=consider-using-dict-items
            dl5, dl15, dl30 = self._dl_peak[rnti]
            ul5, ul15, ul30 = self._ul_peak[rnti]
            metrics.ue_array.append(
                UeMetrics(
                    rnti=rnti,
                    dl_av_5_samples=dl5,
                    dl_av_15_samples=dl15,
                    dl_av_30_samples=dl30,
                    ul_av_5_samples=ul5,
                    ul_av_15_samples=ul15,
                    ul_av_30_samples=ul30,
                )
            )
        return metrics
