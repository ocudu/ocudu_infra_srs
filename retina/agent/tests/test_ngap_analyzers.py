# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for the NGAP pcap analyzers of the AMF pool test.
"""

import unittest
from types import SimpleNamespace
from typing import Dict, Optional, Sequence

from retina.agent.features.pcap.ngap import (
    DuplicateRanUeNgapIdAnalyzer,
    RegistrationAcceptPerAmfAnalyzer,
    ServiceAcceptPerAmfAnalyzer,
)

# ── Packet factory helpers ────────────────────────────────────────────────────


class _FakeLayer:
    """NGAP layer with the field interface of pyshark: get_field() returns a field with all_fields."""

    def __init__(self, fields: Dict[str, Sequence[str]]) -> None:
        self._fields = fields

    def get_field(self, name: str):
        if name not in self._fields:
            return None
        return SimpleNamespace(all_fields=[SimpleNamespace(show=value) for value in self._fields[name]])


def make_packet(
    ran_ue_ngap_id: int,
    message_types: Sequence[int] = (),
    amf_pointer: Optional[int] = None,
    elements: Sequence[str] = (),
):
    # pyshark names the NAS fields "nas-5gs.<field>"
    fields: Dict[str, Sequence[str]] = {"ngap.RAN_UE_NGAP_ID": [str(ran_ue_ngap_id)]}
    if message_types:
        fields["nas-5gs.mm.message_type"] = [f"{message_type:#x}" for message_type in message_types]
    if amf_pointer is not None:
        fields["nas-5gs.amf_pointer"] = [str(amf_pointer)]
    for element in elements:
        fields[f"ngap.{element}_element"] = ["1"]
    return SimpleNamespace(ngap=_FakeLayer(fields))


def registration_accept(ran_ue_ngap_id: int, amf_pointer: int):
    return make_packet(ran_ue_ngap_id, [0x42], amf_pointer)


def service_request(ran_ue_ngap_id: int, amf_pointer: int):
    # The Service Request is also in the NAS message container, so the packet has it two times
    return make_packet(ran_ue_ngap_id, [0x4C, 0x4C], amf_pointer, ["InitialUEMessage"])


def service_accept(ran_ue_ngap_id: int):
    return make_packet(ran_ue_ngap_id, [0x4E])


def initial_ue_message(ran_ue_ngap_id: int):
    return make_packet(ran_ue_ngap_id, elements=["InitialUEMessage"])


def release_complete(ran_ue_ngap_id: int):
    return make_packet(ran_ue_ngap_id, elements=["UEContextReleaseComplete"])


def run(analyzer, packets):
    for packet in packets:
        analyzer.process(packet)
    return analyzer.report().cu_cp


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRegistrationAcceptPerAmfAnalyzer(unittest.TestCase):
    def test_counts_by_amf_pointer(self):
        result = run(
            RegistrationAcceptPerAmfAnalyzer(),
            [registration_accept(0, 0), registration_accept(1, 1), registration_accept(2, 0)],
        )
        self.assertEqual(dict(result.nof_registration_accept_per_amf_pointer), {0: 2, 1: 1})

    def test_ignores_registration_accept_without_5g_guti(self):
        result = run(RegistrationAcceptPerAmfAnalyzer(), [make_packet(0, [0x42])])
        self.assertEqual(dict(result.nof_registration_accept_per_amf_pointer), {})


class TestServiceAcceptPerAmfAnalyzer(unittest.TestCase):
    def test_counts_by_amf_pointer_of_service_request(self):
        result = run(
            ServiceAcceptPerAmfAnalyzer(),
            [service_request(5, 1), service_request(6, 0), service_accept(6), service_accept(5)],
        )
        self.assertEqual(dict(result.nof_service_accept_per_amf_pointer), {0: 1, 1: 1})

    def test_ignores_service_accept_without_service_request(self):
        result = run(ServiceAcceptPerAmfAnalyzer(), [service_accept(5)])
        self.assertEqual(dict(result.nof_service_accept_per_amf_pointer), {})

    def test_forgets_service_request_at_release(self):
        result = run(
            ServiceAcceptPerAmfAnalyzer(),
            [service_request(5, 1), release_complete(5), service_accept(5)],
        )
        self.assertEqual(dict(result.nof_service_accept_per_amf_pointer), {})


class TestDuplicateRanUeNgapIdAnalyzer(unittest.TestCase):
    def test_counts_id_of_active_ue(self):
        result = run(DuplicateRanUeNgapIdAnalyzer(), [initial_ue_message(1), initial_ue_message(1)])
        self.assertEqual(result.nof_duplicate_ran_ue_ngap_id, 1)

    def test_accepts_id_after_release(self):
        result = run(
            DuplicateRanUeNgapIdAnalyzer(),
            [initial_ue_message(1), release_complete(1), initial_ue_message(1), initial_ue_message(2)],
        )
        self.assertEqual(result.nof_duplicate_ran_ue_ngap_id, 0)


if __name__ == "__main__":
    unittest.main()
