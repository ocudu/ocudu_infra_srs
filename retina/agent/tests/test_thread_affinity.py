# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for pin_thread.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from retina.agent.tools import thread_affinity


def _thread(proc: Path, pid: int, tid: int, name: str) -> None:
    task = proc / str(pid) / "task" / str(tid)
    task.mkdir(parents=True)
    (task / "comm").write_text(name + "\n")


class TestPinThread(unittest.TestCase):
    """Test cases for pin_thread."""

    def test_pins_only_matching_threads(self):
        """Every thread with the exact name is pinned, others are untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _thread(proc, 10, 10, "lteue-avx2")
            _thread(proc, 10, 11, "lteue:s72-tx")
            _thread(proc, 10, 12, "lteue:s72-tx-x")
            with mock.patch.object(thread_affinity.os, "sched_setaffinity") as setaffinity:
                pinned = thread_affinity.pin_thread("lteue:s72-tx", {15}, timeout=1, proc=proc)

        self.assertEqual(pinned, [11])
        setaffinity.assert_called_once_with(11, {15})

    def test_not_found(self):
        """No matching thread before the timeout leaves everything unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(thread_affinity, "sleep"),
                mock.patch.object(thread_affinity.os, "sched_setaffinity") as setaffinity,
            ):
                pinned = thread_affinity.pin_thread("lteue:s72-tx", {15}, timeout=0.01, proc=Path(tmp))

        self.assertEqual(pinned, [])
        setaffinity.assert_not_called()

    def test_owner_exited(self):
        """Stops waiting as soon as the owning process is gone."""
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(thread_affinity.os, "sched_setaffinity") as setaffinity,
                mock.patch.object(thread_affinity, "sleep") as sleep,
            ):
                pinned = thread_affinity.pin_thread(
                    "lteue:s72-tx", {15}, timeout=30, owner_alive=lambda: False, proc=Path(tmp)
                )

        self.assertEqual(pinned, [])
        sleep.assert_not_called()
        setaffinity.assert_not_called()

    def test_setaffinity_error(self):
        """A failed pin is logged and skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _thread(proc, 10, 11, "lteue:s72-tx")
            with mock.patch.object(thread_affinity.os, "sched_setaffinity", side_effect=OSError(22, "EINVAL")):
                pinned = thread_affinity.pin_thread("lteue:s72-tx", {15}, timeout=1, proc=proc)

        self.assertEqual(pinned, [])


if __name__ == "__main__":
    unittest.main()
