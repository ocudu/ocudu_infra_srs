# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
In UE simulator mode, lteue quits on its own and closes the websocket before Stop is called.
The stats poll thread must keep the last stats read before the quit.
"""

import json
import tempfile
import unittest
from pathlib import Path
from threading import Event, Lock
from time import sleep
from typing import Dict

from retina.agent.drivers.amarisoft_ue import AmarisoftUe
from retina.agent.features.json_metrics.amarisoft_ue_metrics import AmarisoftUeMetricsAnalyzer
from retina.agent.parameters import ue_defaults

_JOIN_TIMEOUT = 5


def _make_stats(nof_handovers: int) -> Dict:
    cell = {"dl_bitrate": 0, "ul_bitrate": 0, "dl_err_count": 0, "dl_retx_count": 1, "ul_retx_count": 0}
    return {
        "message": "stats",
        "cells": {"0": cell},
        "counters": {"messages": {"handover_success": nof_handovers}},
    }


class _FakeWebSocket:
    """Amarisoft websocket that closes after `nof_responses` stats responses, like lteue does on quit."""

    def __init__(self, nof_responses: int, nof_timeouts: int = 0) -> None:
        self.connected = True
        self.nof_requests = 0
        self._nof_responses = nof_responses
        self._nof_timeouts = nof_timeouts

    def send_command_and_wait_response(self, **_kwargs) -> Dict:
        self.nof_requests += 1
        if self.nof_requests <= self._nof_timeouts:
            raise TimeoutError
        nof_handovers = self.nof_requests - self._nof_timeouts
        if nof_handovers >= self._nof_responses:
            self.connected = False
        return _make_stats(nof_handovers)


def _make_driver(report_folder: str, websocket: _FakeWebSocket) -> AmarisoftUe:
    driver = object.__new__(AmarisoftUe)
    # pylint: disable=protected-access
    driver._websocket = websocket
    driver._metrics_lock = Lock()
    driver._ue_analyzer = AmarisoftUeMetricsAnalyzer()
    driver._stats_poll_thread = None
    driver._stats_poll_event = Event()
    driver.AMARISOFT_STATS_POLL_PERIOD = 0.01
    driver.get_filepath_in_report_folder = lambda filename: str(Path(report_folder) / filename)
    return driver


class StatsPollTest(unittest.TestCase):
    """The poll thread reads the stats until the websocket closes"""

    def setUp(self) -> None:
        self._report_folder = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._report_folder.cleanup)

    def _wait_poll_end(self, driver: AmarisoftUe) -> None:
        # pylint: disable=protected-access
        thread = driver._stats_poll_thread
        assert thread is not None
        thread.join(_JOIN_TIMEOUT)
        self.assertFalse(thread.is_alive())

    def test_last_stats_before_quit_is_kept(self):
        websocket = _FakeWebSocket(nof_responses=5)
        driver = _make_driver(self._report_folder.name, websocket)

        driver._start_stats_poll()  # pylint: disable=protected-access
        self._wait_poll_end(driver)

        metrics = driver._ue_analyzer.report()  # pylint: disable=protected-access
        self.assertEqual(metrics.aggregate.nof_handovers, 5)
        # Reset-on-query counters are added up over all reads
        self.assertEqual(metrics.aggregate.nof_ko_dl, 5)
        self.assertEqual(websocket.nof_requests, 5)

    def test_poll_continues_after_timeout(self):
        websocket = _FakeWebSocket(nof_responses=3, nof_timeouts=2)
        driver = _make_driver(self._report_folder.name, websocket)

        driver._start_stats_poll()  # pylint: disable=protected-access
        self._wait_poll_end(driver)

        metrics = driver._ue_analyzer.report()  # pylint: disable=protected-access
        self.assertEqual(metrics.aggregate.nof_handovers, 3)

    def test_stop_ends_poll_and_writes_no_more_stats(self):
        websocket = _FakeWebSocket(nof_responses=1_000_000)
        driver = _make_driver(self._report_folder.name, websocket)

        driver._start_stats_poll()  # pylint: disable=protected-access
        sleep(0.1)
        driver._stop_stats_poll()  # pylint: disable=protected-access
        nof_requests = websocket.nof_requests
        sleep(0.1)

        self.assertIsNone(driver._stats_poll_thread)  # pylint: disable=protected-access
        self.assertGreater(nof_requests, 0)
        self.assertEqual(websocket.nof_requests, nof_requests)
        # Every read is in the metrics file, so the file is valid JSON once it is closed
        metrics_file = Path(self._report_folder.name) / ue_defaults.metrics_filename_json
        entries = json.loads(metrics_file.read_text(encoding="utf-8") + "]")
        self.assertEqual(len(entries), nof_requests)


if __name__ == "__main__":
    unittest.main()
