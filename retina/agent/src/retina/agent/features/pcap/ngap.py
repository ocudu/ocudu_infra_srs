# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
NGAP/NRPPa-layer pcap analyzers.
"""

from typing import Dict, List, Optional, Set

from retina.protocol.base_pb2 import CuCpMetrics, Metrics

from retina.agent.features.pcap.analyzer import PcapAnalyzer

# 5GMM message types, see TS 24.501 section 9.7.
_NAS_REGISTRATION_ACCEPT = 0x42
_NAS_SERVICE_REQUEST = 0x4C
_NAS_SERVICE_REJECT = 0x4D
_NAS_SERVICE_ACCEPT = 0x4E


def _field_values(packet, name: str) -> List[str]:
    """
    Returns all the values of a field in the NGAP layer of a packet. A packet can have a field more than one time.

    The NAS messages that NGAP carries are part of the NGAP layer. tshark names their fields "nas_5gs.<field>" and
    pyshark names them "nas-5gs.<field>", so both names are accepted.
    """
    layer = packet.ngap
    for key in (name, name.replace("nas_5gs.", "nas-5gs.", 1)):
        field = layer.get_field(key)
        if field is not None:
            return [item.show for item in field.all_fields]
    return []


def _nas_message_types(packet) -> List[int]:
    """
    Returns the 5GMM message types of the NAS messages in a packet.
    """
    return [int(value, 0) for value in _field_values(packet, "nas_5gs.mm.message_type")]


def _first_amf_pointer(packet) -> Optional[int]:
    """
    Returns the AMF Pointer of the first 5G-GUTI or 5G-S-TMSI in the NAS messages of a packet.
    """
    amf_pointers = _field_values(packet, "nas_5gs.amf_pointer")
    return int(amf_pointers[0]) if amf_pointers else None


def _ran_ue_ngap_id(packet) -> Optional[int]:
    """
    Returns the RAN UE NGAP ID of a UE-associated NGAP message.
    """
    ran_ue_ngap_ids = _field_values(packet, "ngap.RAN_UE_NGAP_ID")
    return int(ran_ue_ngap_ids[0]) if ran_ue_ngap_ids else None


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
        return Metrics(cu_cp=CuCpMetrics(nof_e_cid_measurement_initiation_request=self._count))


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
        return Metrics(cu_cp=CuCpMetrics(nof_e_cid_measurement_initiation_response=self._count))


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
        return Metrics(cu_cp=CuCpMetrics(nof_e_cid_measurement_report=self._count))


class ECidMeasurementResultWithAoaAnalyzer(PcapAnalyzer):
    """
    Counts NRPPa E-CID messages that contain an NR UL AoA result.

    For on-demand measurements, the gNB sends the result in the E-CID Measurement Initiation Response.
    For periodic measurements, the gNB sends the result in the E-CID Measurement Report.
    The gNB sends the NR AoA result as the UL-AoA value of id-AngleOfArrivalNR (3GPP TS 38.455).
    tshark display filter: (nrppa.E_CIDMeasurementInitiationResponse_element || nrppa.E_CIDMeasurementReport_element)
    && nrppa.UL_AoA_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return (
            "(nrppa.E_CIDMeasurementInitiationResponse_element || nrppa.E_CIDMeasurementReport_element)"
            " && nrppa.UL_AoA_element"
        )

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_e_cid_measurement_result_with_aoa=self._count))


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
        return Metrics(cu_cp=CuCpMetrics(nof_trp_information_request=self._count))


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
        return Metrics(cu_cp=CuCpMetrics(nof_trp_information_response=self._count))


class NrDlTdoaMeasurementAnalyzer(PcapAnalyzer):
    """
    Counts LPP ProvideLocationInformation messages with NR DL-TDOA measurements.

    The LPP messages are carried in NAS over NGAP. A target device that fails the measurements sends
    nr-DL-TDOA-Error-r16 instead of the measurements, and that message is not counted.
    tshark display filter: lpp.nr_DL_TDOA_SignalMeasurementInformation_r16_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "lpp.nr_DL_TDOA_SignalMeasurementInformation_r16_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_nr_dl_tdoa_measurements=self._count))


class WriteReplaceWarningRequestAnalyzer(PcapAnalyzer):
    """
    Counts NGAP Write-Replace Warning Request messages.

    Sent by the core (AMF) to trigger a PWS (ETWS/CMAS) broadcast at the gNB.
    tshark display filter: ngap.WriteReplaceWarningRequest_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "ngap.WriteReplaceWarningRequest_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_write_replace_warning_request=self._count))


class WriteReplaceWarningResponseAnalyzer(PcapAnalyzer):
    """
    Counts NGAP Write-Replace Warning Response messages.

    tshark display filter: ngap.WriteReplaceWarningResponse_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "ngap.WriteReplaceWarningResponse_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_write_replace_warning_response=self._count))


class RegistrationAcceptPerAmfAnalyzer(PcapAnalyzer):
    """
    Counts NAS Registration Accept messages by the AMF Pointer of the 5G-GUTI.

    The AMF assigns the 5G-GUTI from its own GUAMI. Thus, the AMF Pointer identifies the AMF that registers the UE,
    also when several AMFs of one AMF Set connect to the CU-CP.
    The NAS messages are ciphered with 5G-EA0. tshark decodes them only with the nas-5gs.null_decipher preference.
    tshark display filter: nas_5gs.mm.message_type == 0x42
    """

    def __init__(self) -> None:
        self._count_per_amf_pointer: Dict[int, int] = {}

    @property
    def display_filter(self) -> str:
        return f"nas_5gs.mm.message_type == {_NAS_REGISTRATION_ACCEPT:#x}"

    def process(self, packet) -> None:
        amf_pointer = _first_amf_pointer(packet)
        if amf_pointer is not None:
            self._count_per_amf_pointer[amf_pointer] = self._count_per_amf_pointer.get(amf_pointer, 0) + 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_registration_accept_per_amf_pointer=self._count_per_amf_pointer))


class ServiceAcceptPerAmfAnalyzer(PcapAnalyzer):
    """
    Counts NAS Service Accept messages by the AMF Pointer of the 5G-S-TMSI in the Service Request of the UE.

    The UE sends its 5G-S-TMSI in the Service Request, and only the AMF of this 5G-S-TMSI knows the UE. Another AMF
    sends a Service Reject. Thus, a Service Accept shows that the CU-CP sent the Service Request to the AMF of the UE.
    The analyzer finds the Service Request of a Service Accept by the RAN UE NGAP ID. The CU-CP can use the RAN UE NGAP
    ID again after the UE context release, so the analyzer forgets the Service Request at the UE Context Release
    Complete.
    tshark display filter:
    nas_5gs.mm.message_type == 0x4c || nas_5gs.mm.message_type == 0x4e || ngap.UEContextReleaseComplete_element
    """

    def __init__(self) -> None:
        self._count_per_amf_pointer: Dict[int, int] = {}
        # RAN UE NGAP ID -> AMF Pointer of the 5G-S-TMSI in the Service Request
        self._pending_service_requests: Dict[int, int] = {}

    @property
    def display_filter(self) -> str:
        return (
            f"nas_5gs.mm.message_type == {_NAS_SERVICE_REQUEST:#x}"
            f" || nas_5gs.mm.message_type == {_NAS_SERVICE_ACCEPT:#x}"
            " || ngap.UEContextReleaseComplete_element"
        )

    def process(self, packet) -> None:
        ran_ue_ngap_id = _ran_ue_ngap_id(packet)
        if ran_ue_ngap_id is None:
            return
        if packet.ngap.get_field("ngap.UEContextReleaseComplete_element") is not None:
            self._pending_service_requests.pop(ran_ue_ngap_id, None)
            return

        message_types = _nas_message_types(packet)
        if _NAS_SERVICE_REQUEST in message_types:
            amf_pointer = _first_amf_pointer(packet)
            if amf_pointer is not None:
                self._pending_service_requests[ran_ue_ngap_id] = amf_pointer
        elif _NAS_SERVICE_ACCEPT in message_types:
            amf_pointer = self._pending_service_requests.pop(ran_ue_ngap_id, None)
            if amf_pointer is not None:
                self._count_per_amf_pointer[amf_pointer] = self._count_per_amf_pointer.get(amf_pointer, 0) + 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_service_accept_per_amf_pointer=self._count_per_amf_pointer))


class ServiceRejectAnalyzer(PcapAnalyzer):
    """
    Counts NAS Service Reject messages.

    An AMF sends a Service Reject when it does not know the 5G-S-TMSI of the UE, f.e. when the CU-CP sends the Service
    Request to an AMF that does not serve the UE.
    tshark display filter: nas_5gs.mm.message_type == 0x4d
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return f"nas_5gs.mm.message_type == {_NAS_SERVICE_REJECT:#x}"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_service_reject=self._count))


class NgResetAnalyzer(PcapAnalyzer):
    """
    Counts NGAP NG Reset messages, from the CU-CP or from the AMF.

    tshark display filter: ngap.NGReset_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "ngap.NGReset_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_ng_reset=self._count))


class ErrorIndicationAnalyzer(PcapAnalyzer):
    """
    Counts NGAP Error Indication messages, from the CU-CP or from the AMF.

    An AMF sends an Error Indication f.e. when it receives a message for a UE that it does not know.
    tshark display filter: ngap.ErrorIndication_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "ngap.ErrorIndication_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_ngap_error_indication=self._count))


class DuplicateRanUeNgapIdAnalyzer(PcapAnalyzer):
    """
    Counts InitialUEMessages with the RAN UE NGAP ID of another UE that has an NG connection.

    The RAN UE NGAP ID identifies a UE in the NG-RAN node, so it must be unique across all the AMFs of the CU-CP
    (TS 38.413 section 9.3.3.2). The analyzer adds the ID at the InitialUEMessage and removes it at the UE Context
    Release Complete. It does not see the IDs of the handover procedures.
    tshark display filter: ngap.InitialUEMessage_element || ngap.UEContextReleaseComplete_element
    """

    def __init__(self) -> None:
        self._count = 0
        self._active_ran_ue_ngap_ids: Set[int] = set()

    @property
    def display_filter(self) -> str:
        return "ngap.InitialUEMessage_element || ngap.UEContextReleaseComplete_element"

    def process(self, packet) -> None:
        ran_ue_ngap_id = _ran_ue_ngap_id(packet)
        if ran_ue_ngap_id is None:
            return
        if packet.ngap.get_field("ngap.UEContextReleaseComplete_element") is not None:
            self._active_ran_ue_ngap_ids.discard(ran_ue_ngap_id)
            return
        if ran_ue_ngap_id in self._active_ran_ue_ngap_ids:
            self._count += 1
        self._active_ran_ue_ngap_ids.add(ran_ue_ngap_id)

    def report(self) -> Metrics:
        return Metrics(cu_cp=CuCpMetrics(nof_duplicate_ran_ue_ngap_id=self._count))
