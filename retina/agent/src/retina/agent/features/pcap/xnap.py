# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
XNAP-layer pcap analyzers.
"""

from retina.protocol.base_pb2 import CuCpMetrics, Metrics

from retina.agent.features.pcap.analyzer import PcapAnalyzer


class HandoverRequestAcknowledgeAnalyzer(PcapAnalyzer):
    """
    Counts XNAP Handover Request Acknowledge messages.

    tshark display filter: xnap.HandoverRequestAcknowledge_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "xnap.HandoverRequestAcknowledge_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_xn_handover_request_acknowledge=self._count))


class RetrieveUEContextRequestAnalyzer(PcapAnalyzer):
    """
    Counts XNAP Retrieve UE Context Request messages.

    Sent by the gNB where a UE resumes from RRC Inactive to the gNB anchoring its context.
    tshark display filter: xnap.RetrieveUEContextRequest_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "xnap.RetrieveUEContextRequest_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_xn_retrieve_ue_context_request=self._count))


class RetrieveUEContextResponseAnalyzer(PcapAnalyzer):
    """
    Counts XNAP Retrieve UE Context Response messages.

    tshark display filter: xnap.RetrieveUEContextResponse_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "xnap.RetrieveUEContextResponse_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_xn_retrieve_ue_context_response=self._count))


class SNStatusTransferAnalyzer(PcapAnalyzer):
    """
    Counts XNAP SN Status Transfer messages.

    tshark display filter: xnap.SNStatusTransfer_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "xnap.SNStatusTransfer_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_sn_status_transfer=self._count))
