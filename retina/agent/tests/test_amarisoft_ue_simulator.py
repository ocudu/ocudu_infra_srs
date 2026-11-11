# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
The Amarisoft UE simulator driver reuses the Amarisoft UE driver, but lteue drives the simulated UEs on its own:
Retina must not create a subscriber per client.
"""

import unittest
from threading import Lock
from unittest.mock import MagicMock, patch

from retina.protocol.base_pb2 import UEDefinition
from retina.protocol.ue_pb2_grpc import UEServicer
from retina.protocol.ue_simulator_pb2_grpc import UESimulatorServicer

from retina.agent.app.parameter_manager import set_parameter
from retina.agent.drivers.amarisoft_ue import AmarisoftUe, LocalAmarisoftUe, LocalAmarisoftUeSimulator
from retina.agent.drivers.ue import UEDriver
from retina.agent.parameters import ue_defaults

_IMSI = "001010123456780"


def _base_definition(*_args, **_kwargs) -> UEDefinition:
    definition = UEDefinition()
    definition.subscriber.imsi = _IMSI
    definition.subscriber.tel = 100
    return definition


def _make_driver(driver_class: type) -> AmarisoftUe:
    driver = object.__new__(driver_class)
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

    def test_exposes_the_simulator_service(self):
        self.assertTrue(issubclass(LocalAmarisoftUeSimulator, UESimulatorServicer))

    def test_amarisoft_methods_win_over_the_unimplemented_servicer_stubs(self):
        self.assertIs(LocalAmarisoftUeSimulator.GetDefinition, AmarisoftUe.GetDefinition)
        self.assertIs(LocalAmarisoftUeSimulator.Start, AmarisoftUe.Start)

    def test_plain_ue_does_not_expose_the_simulator_service(self):
        self.assertTrue(issubclass(LocalAmarisoftUe, UEServicer))
        self.assertFalse(issubclass(LocalAmarisoftUe, UESimulatorServicer))

    def test_simulator_mode(self):
        # pylint: disable=protected-access
        self.assertTrue(_make_driver(LocalAmarisoftUeSimulator)._simulator_mode)
        self.assertFalse(_make_driver(LocalAmarisoftUe)._simulator_mode)


@patch.object(UEDriver, "GetDefinition", side_effect=_base_definition)
class GetDefinitionTest(unittest.TestCase):
    """Subscriber management in GetDefinition"""

    def test_simulator_keeps_the_definition_and_registers_no_subscriber(self, _mock):
        driver = _make_driver(LocalAmarisoftUeSimulator)

        for peer in ("peer-1", "peer-2"):
            definition = driver.GetDefinition(MagicMock(), _context(peer))
            self.assertEqual(definition.subscriber.imsi, _IMSI)
            self.assertEqual(definition.subscriber.tel, 100)

        # pylint: disable=protected-access
        self.assertEqual(driver._subscriber_client_dict, {})
        self.assertEqual(driver._subscriber_count, 0)

    def test_ue_creates_a_subscriber_per_client(self, _mock):
        driver = _make_driver(LocalAmarisoftUe)

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
