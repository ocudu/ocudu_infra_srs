#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Set of functions to handle threads in an easier way
"""

import ctypes
from threading import current_thread, Thread
from time import sleep
from typing import Optional


def kill_thread(thread: Thread, exception: Exception) -> None:
    """
    Killing a thread by generating `exception` in that thread
    :param thread
    :param exception
    """
    # See, for example, http://tomerfiliba.com/recipes/Thread2/
    # for more information about using PyThreadState_SetAsyncExc
    if thread is not None and thread != current_thread() and thread.is_alive() and thread.ident is not None:
        tid = ctypes.c_long(thread.ident)
        error = ctypes.py_object(type(exception))
        while ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, error) > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            sleep(0)  # give time for other threads


def join_thread(thread: Thread, timeout: Optional[float] = None, check_alive_step: float = 1) -> None:
    """
    Non blocking joining thread operation.
    It raises TimeoutError if can't join after `timeout` seconds.
    :param thread
    :param timeout
    """
    if thread is not None and thread != current_thread():
        while thread.is_alive():
            thread.join(check_alive_step)
            if timeout is not None:
                timeout -= check_alive_step
                if timeout is not None and timeout <= 0:
                    raise TimeoutError("Timeout reached")
