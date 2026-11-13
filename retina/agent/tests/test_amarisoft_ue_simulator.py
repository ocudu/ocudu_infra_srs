# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
The Amarisoft UE simulator driver is a sibling of the Amarisoft UE driver: both share the lteue process logic
(AmarisoftUeBase), but lteue drives the simulated UEs on its own, so the simulator has no per-client subscriber
and no UE gRPC service.
"""

import unittest
from threading import Lock
from unittest.mock import MagicMock, patch

from retina.protocol.base_pb2 import UEDefinition
from retina.protocol.ue_pb2_grpc import UEServicer
from retina.protocol.ue_simulator_pb2_grpc import UESimulatorServicer

from retina.agent.app.parameter_manager import set_parameter
from retina.agent.drivers import ue_simulator
from retina.agent.drivers.amarisoft_ue import (
    AmarisoftUe,
    AmarisoftUeBase,
    AmarisoftUeSimulator,
    LocalAmarisoftUe,
    LocalAmarisoftUeSimulator,
)
from retina.agent.drivers.ue import UEDriver
from retina.agent.drivers.ue_simulator import UESimulatorDriver
from retina.agent.parameters import ue_defaults

_IMSI = "001010123456780"


def _base_definition(*_args, **_kwargs) -> UEDefinition:
    definition = UEDefinition()
    definition.subscriber.imsi = _IMSI
    definition.subscriber.tel = 100
    return definition


def _make_ue_driver() -> AmarisoftUe:
    driver = object.__new__(LocalAmarisoftUe)
    # pylint: disable=protected-access
    driver._subscriber_client_dict = {}
    driver._subscriber_count = 0
    driver._amarisoft_lock = Lock()
    return driver


def _context(peer: str) -> MagicMock:
    context = MagicMock()
    context.peer.return_value = peer
    return context


class SimulatorDriverTest(unittest.TestCase):
    """Driver class wiring"""

    def test_exposes_only_the_simulator_service(self):
        self.assertTrue(issubclass(LocalAmarisoftUeSimulator, UESimulatorServicer))
        self.assertFalse(issubclass(LocalAmarisoftUeSimulator, UEServicer))

    def test_is_a_sibling_of_the_amarisoft_ue(self):
        self.assertTrue(issubclass(LocalAmarisoftUeSimulator, UESimulatorDriver))
        self.assertTrue(issubclass(LocalAmarisoftUeSimulator, AmarisoftUeBase))
        self.assertFalse(issubclass(LocalAmarisoftUeSimulator, AmarisoftUe))
        self.assertFalse(issubclass(LocalAmarisoftUeSimulator, UEDriver))

    def test_does_not_inherit_ue_only_methods(self):
        for name in ("IPerf", "WaitUntilAttached", "_ue_get", "_validate_state", "_parse_metrics"):
            self.assertFalse(hasattr(LocalAmarisoftUeSimulator, name), name)

    def test_simulator_methods_win_over_the_unimplemented_servicer_stubs(self):
        self.assertIs(LocalAmarisoftUeSimulator.GetDefinition, UESimulatorDriver.GetDefinition)
        self.assertIs(LocalAmarisoftUeSimulator.Start, AmarisoftUeSimulator.Start)

    def test_plain_ue_does_not_expose_the_simulator_service(self):
        self.assertTrue(issubclass(LocalAmarisoftUe, UEServicer))
        self.assertFalse(issubclass(LocalAmarisoftUe, UESimulatorServicer))

    def test_ue_simulator_mode_parameter_is_gone(self):
        # The mode comes from the driver class, not from a parameter
        self.assertFalse(hasattr(ue_defaults, "ue_simulator_mode"))


class GetDefinitionTest(unittest.TestCase):
    """Subscriber management in GetDefinition"""

    @patch.object(ue_simulator, "build_ue_definition", side_effect=_base_definition)
    def test_simulator_keeps_the_definition_for_every_client(self, _mock):
        driver = object.__new__(LocalAmarisoftUeSimulator)

        for peer in ("peer-1", "peer-2"):
            definition = driver.GetDefinition(MagicMock(), _context(peer))
            self.assertEqual(definition.subscriber.imsi, _IMSI)
            self.assertEqual(definition.subscriber.tel, 100)

    @patch.object(UEDriver, "GetDefinition", side_effect=_base_definition)
    def test_ue_creates_a_subscriber_per_client(self, _mock):
        driver = _make_ue_driver()

        imsi_1 = driver.GetDefinition(MagicMock(), _context("peer-1")).subscriber.imsi
        imsi_2 = driver.GetDefinition(MagicMock(), _context("peer-2")).subscriber.imsi
        imsi_1_again = driver.GetDefinition(MagicMock(), _context("peer-1")).subscriber.imsi

        self.assertEqual(imsi_1, "001010123456781")
        self.assertEqual(imsi_2, "001010123456782")
        self.assertEqual(imsi_1_again, imsi_1)
        # pylint: disable=protected-access
        self.assertEqual(driver._subscriber_count, 2)


class ParameterNamespaceTest(unittest.TestCase):
    """A ue_simulator node pushes `ue_simulator.<key>` parameters"""

    def setUp(self) -> None:
        old_apn = ue_defaults.apn
        self.addCleanup(setattr, ue_defaults, "apn", old_apn)

    def test_ue_simulator_namespace_sets_the_ue_parameters(self):
        set_parameter("ue_simulator.apn", "simulator-apn")
        self.assertEqual(ue_defaults.apn, "simulator-apn")

    def test_ue_namespace_still_works(self):
        set_parameter("ue.apn", "ue-apn")
        self.assertEqual(ue_defaults.apn, "ue-apn")


if __name__ == "__main__":
    unittest.main()
