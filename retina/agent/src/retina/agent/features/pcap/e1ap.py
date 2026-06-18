# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
E1AP-layer pcap analyzers.
"""

from retina.protocol.base_pb2 import CuCpMetrics, Metrics

from retina.agent.features.pcap.analyzer import PcapAnalyzer


class RohcProfile1Analyzer(PcapAnalyzer):
    """
    Counts E1AP frames where rOHC Profile 1 (RTP/UDP/IP) is configured on a DRB.

    Profile 1 is specific to VoNR speech bearers (5QI=1). It only appears in
    BearerContextSetup/Modification when the 5GC requests GBR VoNR bearers with
    RoHC compression — it is absent in non-VoNR tests.
    tshark display filter: e1ap.rOHC_Profiles == 1
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "e1ap.rOHC_Profiles == 1"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_rohc_profile_1_configured=self._count))


class RohcProfile2Analyzer(PcapAnalyzer):
    """
    Counts E1AP frames where rOHC Profile 2 (UDP/IP) is configured on a DRB.

    Profile 2 is used for VoNR RTCP bearers (5QI=2).
    tshark display filter: e1ap.rOHC_Profiles == 2
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "e1ap.rOHC_Profiles == 2"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_rohc_profile_2_configured=self._count))


class Fiveqi1DrbAnalyzer(PcapAnalyzer):
    """
    Counts E1AP frames configuring a DRB with 5QI=1 (VoNR speech bearer).
    tshark display filter: e1ap.fiveQI == 1
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "e1ap.fiveQI == 1"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_5qi_1_drb_configured=self._count))


class Fiveqi2DrbAnalyzer(PcapAnalyzer):
    """
    Counts E1AP frames configuring a DRB with 5QI=2 (VoNR RTCP bearer).
    tshark display filter: e1ap.fiveQI == 2
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "e1ap.fiveQI == 2"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_5qi_2_drb_configured=self._count))


class Fiveqi5DrbAnalyzer(PcapAnalyzer):
    """
    Counts E1AP frames configuring a DRB with 5QI=5 (IMS signaling bearer).
    tshark display filter: e1ap.fiveQI == 5
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "e1ap.fiveQI == 5"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_5qi_5_drb_configured=self._count))
