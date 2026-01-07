#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Contains a class to check if a timeout has been reached and related logic
"""

import time
from typing import Optional


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

    def cancel(self) -> None:
        """
        Cancel the timeout
        """
        self._time_to_reach = 0
        self._msg = "Timeout cancelled"
