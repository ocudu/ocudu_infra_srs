# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for the backhaul (N2/N3) address selection of a request.
"""

import ipaddress
import unittest
from unittest import mock

from retina.orchestrator.requirement import RequirementManager
from retina.orchestrator.reservation.managers import get_pool_request_reservation_from_config
from retina.orchestrator.reservation.resources import RequestReservation, ResourceList, get_loopback_address


def _request(**kwargs) -> RequestReservation:
    return RequestReservation(
        name="amarisoft-mme",
        type_r="5gc",
        image="image",
        nof_ports=1,
        labels=[],
        resources=ResourceList([]),
        requirement_manager=RequirementManager({}, []),
        binary_list=[],
        environment=[],
        **kwargs,
    )


class TestGetLoopbackAddress(unittest.TestCase):
    """Test cases for get_loopback_address."""

    def test_is_loopback_outside_127_0(self):
        """Addresses are in 127/8 but never in 127.0.x.x."""
        for orch_id in ("a", "b", "orch-1234", ""):
            address = ipaddress.IPv4Address(get_loopback_address(orch_id, 1))
            self.assertTrue(address.is_loopback)
            self.assertNotEqual(address.packed[1], 0)

    def test_deterministic_and_indexed(self):
        """Same orchestration shares the prefix, the index sets the last octet."""
        first = get_loopback_address("orch", 1)
        second = get_loopback_address("orch", 2)
        self.assertEqual(first, get_loopback_address("orch", 1))
        self.assertEqual(first.rsplit(".", 1)[0], second.rsplit(".", 1)[0])
        self.assertTrue(first.endswith(".1"))
        self.assertTrue(second.endswith(".2"))

    def test_index_out_of_range(self):
        """Index must fit in the last octet without being network or broadcast."""
        for index in (0, 255):
            with self.assertRaises(ValueError):
                get_loopback_address("orch", index)


class TestBackhaulAddress(unittest.TestCase):
    """Test cases for RequestReservation.get_backhaul_ip."""

    def test_default_uses_pod_network(self):
        """Without backhaul settings there is no backhaul address and no host network."""
        req = _request()
        k_server = mock.Mock()
        self.assertEqual(req.get_backhaul_ip(k_server), "")
        self.assertFalse(req.get_enable_network_connection(k_server))

    def test_loopback(self):
        """Loopback returns the assigned address and forces the host network."""
        req = _request(ip_back_source="loopback", loopback_address="127.1.2.1")
        k_server = mock.Mock()
        self.assertEqual(req.get_backhaul_ip(k_server), "127.1.2.1")
        self.assertTrue(req.get_enable_network_connection(k_server))
        k_server.get_cluster_configuration.assert_not_called()

    def test_loopback_without_address(self):
        """Loopback without an assigned address is an error, not a silent pod-network fallback."""
        req = _request(ip_back_source="loopback")
        with self.assertRaises(ValueError):
            req.get_backhaul_ip(mock.Mock())


class TestLoopbackAssignment(unittest.TestCase):
    """Test cases for loopback assignment when building the request pool."""

    def test_unique_per_loopback_request(self):
        """Each loopback request gets its own address; others get none."""
        config = [
            {"name": "gnb", "image": "i", "ip_back_source": "loopback"},
            {"name": "ue", "image": "i"},
            {"name": "5gc", "image": "i", "ip_back_source": "loopback"},
        ]
        pool = get_pool_request_reservation_from_config(config, orch_id="orch", user_name="user")
        addresses = {req.name: req.loopback_address for req in pool.request_reservation_list}
        self.assertEqual(addresses["gnb"], get_loopback_address("orch", 1))
        self.assertEqual(addresses["5gc"], get_loopback_address("orch", 2))
        self.assertEqual(addresses["ue"], "")


if __name__ == "__main__":
    unittest.main()
