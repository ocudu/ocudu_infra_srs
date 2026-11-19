# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Pin threads that the software under test creates to specific CPUs
"""

import logging
import os
from pathlib import Path
from time import monotonic, sleep
from typing import Callable, Collection, List


def _find_threads(name: str, proc: Path) -> List[int]:
    # tids of every thread in this PID namespace named `name`
    found: List[int] = []
    for comm in proc.glob("[0-9]*/task/[0-9]*/comm"):
        try:
            if comm.read_text(encoding="utf-8").strip() == name:
                found.append(int(comm.parent.name))
        except (OSError, ValueError):
            continue
    return found


def pin_thread(
    name: str,
    cpus: Collection[int],
    timeout: float,
    owner_alive: Callable[[], bool] = lambda: True,
    proc: Path = Path("/proc"),
) -> List[int]:
    """
    Wait up to `timeout` seconds for threads named `name` and restrict them to `cpus`.
    Stops waiting as soon as `owner_alive` returns False.
    Returns the tids pinned (empty if none showed up).
    """
    deadline = monotonic() + timeout
    found = _find_threads(name, proc)
    while not found and monotonic() < deadline:
        if not owner_alive():
            logging.warning("Process exited before thread %s appeared, affinity unchanged", name)
            return []
        sleep(0.05)
        found = _find_threads(name, proc)

    pinned: List[int] = []
    for tid in found:
        try:
            os.sched_setaffinity(tid, cpus)
        except OSError as err:
            logging.warning("Can't pin %s (tid %d) to CPUs %s: %s", name, tid, sorted(cpus), err)
            continue
        logging.info("Thread %s (tid %d) pinned to CPUs %s", name, tid, sorted(cpus))
        pinned.append(tid)
    if not found:
        logging.warning("Thread %s not found after %.0f s, affinity unchanged", name, timeout)
    return pinned
