# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
CU-CP pass/fail criteria definitions
"""

import operator

from google.protobuf.wrappers_pb2 import UInt32Value
from retina.launcher.criteria import CuCpCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class errors_le(CuCpCriteria):
    """Errors"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.Stop.with_call(UInt32Value(value=15), timeout=15)[0].error_count for s in self._stub_array)


class warnings_le(CuCpCriteria):
    """Warnings"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.Stop.with_call(UInt32Value(value=15), timeout=15)[0].warning_count for s in self._stub_array)
