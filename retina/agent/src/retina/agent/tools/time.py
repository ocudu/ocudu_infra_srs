# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Time related utilities
"""

import time
from datetime import datetime, timezone
from typing import Optional


def now_timestamp_file() -> str:
    """Get current timestamp in a format valid for file and folder names"""
    return datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")


def now_utc_timestamp() -> str:
    """Get current UTC timestamp"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}"


class TimeoutHandler:
    """
    Checks if a timeout has been reached and related logic
    """

    def __init__(self, timeout: Optional[float] = -1, msg: str = "Timeout reached") -> None:
        """
        If timeout <= 0, it will wait forever
        """
        self._time_to_reach = None if (timeout is None or timeout <= 0) else time.time() + timeout
        self._msg = msg

    def not_reached(self) -> bool:
        """
        It will return true if the timeout has not been reached.
        If not, It will raise a TimeoutError
        """
        if self._time_to_reach is not None and time.time() >= self._time_to_reach:
            raise TimeoutError(self._msg)
        return True

    def get_remaining_timeout(self) -> float:
        """
        It will return the remaining timeout, if >0
        If original timeout has been reached, It will raise a TimeoutError
        If the original timeout was <=0, it will return -1
        """
        if self._time_to_reach is None:
            return -1  # Special value for no wait
        remaining_timeout = self._time_to_reach - time.time()
        if remaining_timeout <= 0:
            raise TimeoutError(self._msg)
        return remaining_timeout
