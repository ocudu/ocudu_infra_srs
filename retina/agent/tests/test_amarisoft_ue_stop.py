# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
A Stop from an unknown client powers off every started virtual UE.
Stopping the last one clears the subscriber dict while it is being iterated.
"""

import unittest
from threading import Event

from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import Subscriber

from retina.agent.drivers.amarisoft_ue import AmarisoftUe
from retina.agent.drivers.ue import SubscriberWithStatus


def _make_driver(nof_ues: int) -> AmarisoftUe:
    driver = object.__new__(AmarisoftUe)
    # pylint: disable=protected-access
    # No websocket: each UE takes the "can not stop in a safe way" path
    driver._websocket = None
    driver._process = None
    driver._stats_poll_thread = None
    driver._stats_poll_event = Event()
    driver._subscriber_count = nof_ues
    driver._subscriber_client_dict = {
        f"peer{i}": SubscriberWithStatus(Subscriber(), i + 1, started=True) for i in range(nof_ues)
    }
    return driver


class StopUnknownClientTest(unittest.TestCase):
    """Stop from an unknown client stops all virtual UEs"""

    def _check_stop_all(self, nof_ues: int) -> None:
        driver = _make_driver(nof_ues)
        # pylint: disable=protected-access
        self.assertIsNone(driver._stop_unlock(UInt32Value(), "unknown"))
        self.assertEqual(driver._subscriber_client_dict, {})
        self.assertEqual(driver._subscriber_count, 0)

    def test_single_ue(self):
        """Only one started UE"""
        self._check_stop_all(1)

    def test_multiple_ues(self):
        """Several started UEs, as in MOCN"""
        self._check_stop_all(3)


if __name__ == "__main__":
    unittest.main()
