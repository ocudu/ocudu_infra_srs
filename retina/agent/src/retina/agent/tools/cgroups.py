#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
This module provides tools for monitoring and checking cgroup metrics such as memory events,
CPU throttling, and pressure metrics for CPU, Memory, and I/O. It includes functions to read
cgroup files and log warnings or errors based on the metrics obtained.
"""

import logging
import os


def _get_cgroup_path() -> str:
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                parts = line.strip().split(":")
                if len(parts) == 3:
                    cgroup_path = parts[2]
                    full_path = os.path.join("/sys/fs/cgroup", cgroup_path.lstrip("/"))
                    if os.path.exists(full_path):
                        return full_path
    except FileNotFoundError:
        logging.warning("Could not read /proc/self/cgroup. Are you in a container?")

    return "/sys/fs/cgroup"


def _read_cgroup_file(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return {line.split()[0]: int(line.split()[1]) for line in f.readlines()}
        except (OSError, ValueError) as e:
            logging.warning("Error reading %s: %s", file_path, e)
    return {}


def _check_oom_kill(base_cgroup_path: str):
    for filename in ("memory.events", "memory/memory.oom_control"):
        data = _read_cgroup_file(os.path.join(base_cgroup_path, filename))
        if data.get("oom_kill", 0) > 0:
            logging.error("OOM Kill detected - %d processes terminated due to lack of memory.", data["oom_kill"])
            break


def _check_cpu_throttling(base_cgroup_path: str):
    for filename in ("cpu.stat", "cpu/cpu.stat"):
        data = _read_cgroup_file(os.path.join(base_cgroup_path, filename))
        if data.get("nr_throttled", 0) > 0:
            logging.warning("CPU Throttling detected - %d times the CPU has been throttled.", data["nr_throttled"])
            break


# pylint: disable=too-many-nested-blocks
def _check_pressure(base_cgroup_path: str):
    pressure_files = {
        "CPU": os.path.join(base_cgroup_path, "cpu.pressure"),
        "Memory": os.path.join(base_cgroup_path, "memory.pressure"),
        "I/O": os.path.join(base_cgroup_path, "io.pressure"),
    }

    for resource, file_path in pressure_files.items():
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0]
                        avg10 = float(parts[1].split("=")[1])

                        if avg10 > 1.0:
                            logging.warning("%s Pressure detected - %s avg10=%f", resource, key, avg10)
            except (OSError, ValueError) as e:
                logging.warning("Error reading %s: %s", file_path, e)


def log_cgroups_warnings_and_errors():
    """
    Logs warnings and errors for cgroup metrics such as memory events, CPU throttling, and pressure.

    Raises:
        None: Any exceptions encountered during file reading are logged as warnings.
    """
    base_cgroup_path = _get_cgroup_path()
    if base_cgroup_path:
        _check_oom_kill(base_cgroup_path)
        _check_cpu_throttling(base_cgroup_path)
        _check_pressure(base_cgroup_path)
