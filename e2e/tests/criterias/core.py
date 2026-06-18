# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
5GC pass/fail criteria definitions.
"""

import operator

from google.protobuf.empty_pb2 import Empty
from retina.launcher.criteria import FiveGcCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class nof_pdu_session_establishment_accept_eq(FiveGcCriteria):
    """PDU Session Establishment Accept"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_pdu_session_establishment_accept for s in self._stub_array)


class nof_pdu_session_establishment_accept_ge(FiveGcCriteria):
    """PDU Session Establishment Accept"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_pdu_session_establishment_accept for s in self._stub_array)


class nof_nas_service_accept_eq(FiveGcCriteria):
    """NAS Service Accept"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_nas_service_accept for s in self._stub_array)


class nof_ng_paging_eq(FiveGcCriteria):
    """NG Paging"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_ng_paging for s in self._stub_array)


class nof_pdu_session_modification_complete_eq(FiveGcCriteria):
    """PDU Session Modification Complete"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_pdu_session_modification_complete for s in self._stub_array)


class nof_pdu_session_modification_complete_ge(FiveGcCriteria):
    """PDU Session Modification Complete"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_pdu_session_modification_complete for s in self._stub_array)


class nof_pdu_session_modification_command_reject_eq(FiveGcCriteria):
    """PDU Session Modification Command Reject"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_pdu_session_modification_command_reject for s in self._stub_array)


class nof_ims_nas_registered_ue_eq(FiveGcCriteria):
    """IMS NAS Registered UE"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_ims_nas_registered_ue for s in self._stub_array)
