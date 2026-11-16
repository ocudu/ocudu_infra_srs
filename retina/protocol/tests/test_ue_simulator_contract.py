# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
UESimulator must be a subset of UE.

The e2e steps drive a UE and a UE simulator through the same code (GetDefinition, Start). proto3 has no service
inheritance and the generated stubs are untyped, so nothing else catches a drift between both .proto files.
"""

import unittest
from typing import List, Tuple

from google.protobuf.descriptor import MethodDescriptor, ServiceDescriptor

from retina.protocol import ric_pb2, ue_pb2, ue_simulator_pb2


def _signature(method: MethodDescriptor) -> Tuple[str, str, bool, bool]:
    """Everything a caller depends on: request type, response type and streaming mode."""
    return (
        method.input_type.full_name,
        method.output_type.full_name,
        method.client_streaming,
        method.server_streaming,
    )


def _subset_mismatches(subset_service: ServiceDescriptor, superset_service: ServiceDescriptor) -> List[str]:
    """RPCs of `subset_service` that are missing from, or different in, `superset_service`."""
    mismatches = []
    for method in subset_service.methods:
        other = superset_service.methods_by_name.get(method.name)
        if other is None:
            mismatches.append(f"{method.name} is missing from {superset_service.name}")
        elif _signature(method) != _signature(other):
            mismatches.append(
                f"{method.name}: {subset_service.name} (request, response, client_streaming, server_streaming)="
                f"{_signature(method)} != {superset_service.name} {_signature(other)}"
            )
    return mismatches


_UE = ue_pb2.DESCRIPTOR.services_by_name["UE"]
_UE_SIMULATOR = ue_simulator_pb2.DESCRIPTOR.services_by_name["UESimulator"]


class UESimulatorIsSubsetOfUE(unittest.TestCase):
    """Every UESimulator RPC must exist in UE with the same signature"""

    def test_every_ue_simulator_rpc_exists_in_ue_with_the_same_signature(self):
        self.assertEqual(_subset_mismatches(_UE_SIMULATOR, _UE), [])

    def test_ue_simulator_is_not_empty(self):
        # An empty service would make the subset check pass trivially
        self.assertGreater(len(_UE_SIMULATOR.methods), 0)

    def test_the_check_detects_a_mismatch(self):
        # NearRtRic also has GetDefinition and Start, but with other request / response types
        ric = ric_pb2.DESCRIPTOR.services_by_name["NearRtRic"]
        mismatches = _subset_mismatches(_UE_SIMULATOR, ric)
        self.assertEqual(len(mismatches), 2)
        self.assertTrue(any(m.startswith("GetDefinition:") for m in mismatches))
        self.assertTrue(any(m.startswith("Start:") for m in mismatches))

    def test_the_check_detects_a_missing_rpc(self):
        # UE has RPCs (e.g. WaitUntilAttached) that UESimulator doesn't
        mismatches = _subset_mismatches(_UE, _UE_SIMULATOR)
        self.assertIn("WaitUntilAttached is missing from UESimulator", mismatches)


if __name__ == "__main__":
    unittest.main()
