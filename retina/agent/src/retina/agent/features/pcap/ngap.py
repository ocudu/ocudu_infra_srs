# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
NGAP/NRPPa-layer pcap analyzers.
"""

from retina.protocol.base_pb2 import CoreMetrics, Metrics

from retina.agent.features.pcap.analyzer import PcapAnalyzer


class ECidMeasurementInitiationRequestAnalyzer(PcapAnalyzer):
    """
    Counts NRPPa E-CID Measurement Initiation Request messages.

    tshark display filter: nrppa.E_CIDMeasurementInitiationRequest_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "nrppa.E_CIDMeasurementInitiationRequest_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(core=CoreMetrics(nof_e_cid_measurement_initiation_request=self._count))


class ECidMeasurementInitiationResponseAnalyzer(PcapAnalyzer):
    """
    Counts NRPPa E-CID Measurement Initiation Response messages.

    tshark display filter: nrppa.E_CIDMeasurementInitiationResponse_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "nrppa.E_CIDMeasurementInitiationResponse_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(core=CoreMetrics(nof_e_cid_measurement_initiation_response=self._count))


class ECidMeasurementReportAnalyzer(PcapAnalyzer):
    """
    Counts NRPPa E-CID Measurement Report messages.

    tshark display filter: nrppa.E_CIDMeasurementReport_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "nrppa.E_CIDMeasurementReport_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(core=CoreMetrics(nof_e_cid_measurement_report=self._count))


class TrpInformationRequestAnalyzer(PcapAnalyzer):
    """
    Counts NRPPa TRP Information Request messages.

    tshark display filter: nrppa.TRPInformationRequest_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "nrppa.TRPInformationRequest_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(core=CoreMetrics(nof_trp_information_request=self._count))


class TrpInformationResponseAnalyzer(PcapAnalyzer):
    """
    Counts NRPPa TRP Information Response messages.

    tshark display filter: nrppa.TRPInformationResponse_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "nrppa.TRPInformationResponse_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(core=CoreMetrics(nof_trp_information_response=self._count))
