# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
5G NR MAC-layer pcap analyzers.
"""

from typing import List

from retina.protocol.base_pb2 import DuMetrics, Metrics

from retina.agent.features.pcap.analyzer import PcapAnalyzer


class DifferentialKoffsetAnalyzer(PcapAnalyzer):
    """
    Collects the Differential Koffsets signalled to a UE in a MAC-NR capture.

    The MAC CE carries the value a UE subtracts from the cell-specific Koffset, 6 bits as per
    TS 38.321, 6.1.3.57. Any value at all means the cell derived a UE-specific Koffset and told
    the UE about it.

    The cell only signals a value that differs from the one the UE applies, so each entry is a
    derivation that followed the UE round trip. A retransmitted MAC CE, and a value signalled
    again after one was lost, repeat the value in force, so a value is recorded only when it
    differs from the one before it.
    tshark display filter: mac-nr.differential_koffset
    """

    def __init__(self) -> None:
        self._koffset_array: List[int] = []

    @property
    def display_filter(self) -> str:
        return "mac-nr.differential_koffset"

    def process(self, packet) -> None:
        try:
            value = int(packet["mac-nr"].differential_koffset)
        except (AttributeError, KeyError, ValueError):
            return
        if not self._koffset_array or self._koffset_array[-1] != value:
            self._koffset_array.append(value)

    def report(self) -> Metrics:
        return Metrics(du=DuMetrics(differential_koffset_array=self._koffset_array))
