#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Exception Management
"""

import inspect
import sys
import traceback
from types import TracebackType

import grpc

from retina.client.input.entrypoint import RetinaEntrypoint


def retina_except_hook(exception_type, value, tb_obj):
    """
    Exception hook customization to pretty print rpc errors
    """

    if isinstance(value, grpc.RpcError):
        traceback.print_exception(
            ErrorReportedByAgent,
            ErrorReportedByAgent(value),
            tb_obj,
            limit=_count_non_grpc_entries_in_traceback(tb_obj),
        )
    else:
        sys.__excepthook__(exception_type, value, tb_obj)


def clean_grpc_traceback(tb_obj: TracebackType):
    """
    Remove pure grpc entries in the traceback.
    It modifies tb_obj
    """
    for _ in range(_count_non_grpc_entries_in_traceback(tb_obj) - 1):
        if tb_obj.tb_next is not None:
            tb_obj = tb_obj.tb_next
    tb_obj.tb_next = None


def _count_non_grpc_entries_in_traceback(tb_obj: TracebackType) -> int:
    """
    Return number of entries in traceback without counting pure grpc internal traces
    """
    limit = -1
    for limit, frame_summary in enumerate(traceback.extract_tb(tb_obj)):
        filename, *_ = frame_summary
        if (grpc.__file__.replace("__init__.py", "") in filename) or (
            filename
            in (
                __file__,
                inspect.getfile(RetinaEntrypoint),
            )
        ):
            return limit
    return limit


class ErrorReportedByAgent(grpc.RpcError):
    """
    Exception class to customize representation
    """

    # When printing the exception, it will do it as "ErrorReportedByAgent"
    # instead of "retina.client...ErrorReportedByAgent"
    __module__ = "builtins"

    def __init__(self, error) -> None:
        self.code: grpc.StatusCode = error._state.code
        self.details: str = error._state.details.strip()

    def __repr__(self) -> str:
        return self.details if self.details else f"RPC method terminated with {self.code}"

    def __str__(self) -> str:
        return self.__repr__()
