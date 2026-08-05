# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
UE pass/fail criteria definitions
"""

import operator

from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.launcher.criteria import UeCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class nof_ko_dl_le(UeCriteria):
    """UE DL KOs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_ko_dl for s in self._stub_array)


class nof_ko_ul_le(UeCriteria):
    """UE UL KOs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_ko_ul for s in self._stub_array)


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


class nof_pdu_session_establishment_accept_eq(UeCriteria):
    """PDU Session Establishment Accept"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_pdu_session_establishment_accept for s in self._stub_array)


class nof_etws_msg_received_ge(UeCriteria):
    """ETWS Secondary Message Received"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_etws_msg_received for s in self._stub_array)


class nof_cmas_msg_received_ge(UeCriteria):
    """CMAS Message Received"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_cmas_msg_received for s in self._stub_array)


class warnings_le(UeCriteria):
    """Warnings"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.Stop.with_call(UInt32Value(value=15), timeout=15)[0].warning_count for s in self._stub_array)
