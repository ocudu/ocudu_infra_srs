# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Stop() must be idempotent: the core/du/cu_cp `errors_le` and `warnings_le` criteria read
their counts by calling Stop again after the test already stopped everything, so a second
call must never overwrite the metrics captured by the first one.
"""

import tempfile
import unittest
from pathlib import Path
from typing import Dict
from unittest.mock import patch

from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import Metrics, StopResponse

from retina.agent.drivers.amarisoft_5gc import _AmarisoftIms, _AmarisoftMme
from retina.agent.drivers.fivegc import FiveGCDriver

_STATS = {
    "counters": {
        "messages": {
            "5gs_nas_pdu_session_establishment_accept": 1,
            "5gs_nas_service_accept": 1,
            "ng_paging": 1,
        }
    }
}

_USERS = {"users": [{"impi": "001010123456780@ims.mnc001.mcc001.3gppnetwork.org"}]}


class _FakeWebSocket:
    """Amarisoft websocket that stops answering once quit() closed it."""

    def __init__(self, response: Dict) -> None:
        self._response = response
        self.connected = True
        self.nof_commands = 0

    def send_command_and_wait_response(self, **_kwargs) -> Dict:
        self.nof_commands += 1
        return self._response if self.connected else {}

    def quit(self) -> None:
        self.connected = False


def _make_driver(driver_cls, report_folder: str, websocket: _FakeWebSocket):
    driver = object.__new__(driver_cls)
    # pylint: disable=protected-access
    driver._websocket = websocket
    driver._metrics = Metrics()
    driver._nof_lates = 0
    driver._nof_under = 0
    driver._nof_seq_err = 0
    driver.get_filepath_in_report_folder = lambda filename: str(Path(report_folder) / filename)
    return driver


class StopIdempotencyTest(unittest.TestCase):
    """Repeated Stop calls must preserve the metrics of the first one"""

    def setUp(self) -> None:
        self._report_folder = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._report_folder.cleanup)
        patcher = patch.object(FiveGCDriver, "Stop", return_value=StopResponse())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_mme_metrics_survive_a_second_stop(self):
        websocket = _FakeWebSocket(_STATS)
        mme = _make_driver(_AmarisoftMme, self._report_folder.name, websocket)

        mme.Stop(UInt32Value(value=0), None)
        first = mme.GetMetrics(None, None)
        self.assertEqual(first.core.nof_ng_paging, 1)
        self.assertEqual(first.core.nof_nas_service_accept, 1)
        self.assertEqual(first.core.nof_pdu_session_establishment_accept, 1)

        for _ in range(3):
            mme.Stop(UInt32Value(value=0), None)

        self.assertEqual(mme.GetMetrics(None, None), first)
        # The closed websocket must not be polled again
        self.assertEqual(websocket.nof_commands, 1)

    def test_mme_metrics_file_written_once(self):
        websocket = _FakeWebSocket(_STATS)
        mme = _make_driver(_AmarisoftMme, self._report_folder.name, websocket)

        for _ in range(3):
            mme.Stop(UInt32Value(value=0), None)

        written = [path.read_text(encoding="utf-8") for path in Path(self._report_folder.name).iterdir()]
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0].count("["), 1)

    def test_ims_metrics_survive_a_second_stop(self):
        websocket = _FakeWebSocket(_USERS)
        ims = _make_driver(_AmarisoftIms, self._report_folder.name, websocket)
        ims._plmn = type("PLMN", (), {"mcc": "001", "mnc": "01"})()  # pylint: disable=protected-access
        ims._subscriber_array = [  # pylint: disable=protected-access
            type("Subscriber", (), {"imsi": "001010123456780"})()
        ]

        ims.Stop(UInt32Value(value=0), None)
        first = ims.GetMetrics(None, None)
        self.assertEqual(first.core.nof_ims_nas_registered_ue, 1)

        for _ in range(3):
            ims.Stop(UInt32Value(value=0), None)

        self.assertEqual(ims.GetMetrics(None, None), first)
        self.assertEqual(websocket.nof_commands, 1)


if __name__ == "__main__":
    unittest.main()
