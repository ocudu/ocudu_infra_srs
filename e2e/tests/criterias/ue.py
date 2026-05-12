# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
UE pass/fail criteria definitions
"""

import operator

from google.protobuf.empty_pb2 import Empty
from retina.launcher.criteria import UeCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class nof_handovers_eq(UeCriteria):
    """Handovers"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_handovers for s in self._stub_array)


class nof_handovers_ge(UeCriteria):
    """Handovers"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_handovers for s in self._stub_array)
