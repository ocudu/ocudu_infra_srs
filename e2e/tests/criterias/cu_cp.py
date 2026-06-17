# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
CU-CP pass/fail criteria definitions
"""

import operator

from google.protobuf.empty_pb2 import Empty
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


class nof_e_cid_measurement_initiation_request_eq(CuCpCriteria):
    """E-CID Measurement Initiation Request"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_e_cid_measurement_initiation_request for s in self._stub_array)


class nof_e_cid_measurement_initiation_response_eq(CuCpCriteria):
    """E-CID Measurement Initiation Response"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_e_cid_measurement_initiation_response for s in self._stub_array)


class nof_e_cid_measurement_report_geq(CuCpCriteria):
    """E-CID Measurement Report"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_e_cid_measurement_report for s in self._stub_array)


class trp_information_request_eq(CuCpCriteria):
    """TRP Information Request"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_trp_information_request for s in self._stub_array)


class trp_information_response_eq(CuCpCriteria):
    """TRP Information Response"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_trp_information_response for s in self._stub_array)


class nof_xn_handover_request_acknowledge_geq(CuCpCriteria):
    """XN Handover Request Acknowledge"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_xn_handover_request_acknowledge for s in self._stub_array)


class nof_sn_status_transfer_geq(CuCpCriteria):
    """SN Status Transfer"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_sn_status_transfer for s in self._stub_array)


class nof_rohc_profile_1_configured_eq(CuCpCriteria):
    """RoHC Profile 1 DRBs"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_rohc_profile_1_configured for s in self._stub_array)


class nof_rohc_profile_1_configured_ge(CuCpCriteria):
    """RoHC Profile 1 DRBs"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_rohc_profile_1_configured for s in self._stub_array)


class nof_rohc_profile_2_configured_ge(CuCpCriteria):
    """RoHC Profile 2 DRBs"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_rohc_profile_2_configured for s in self._stub_array)


class nof_5qi_1_drb_configured_eq(CuCpCriteria):
    """5QI-1 DRBs"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_5qi_1_drb_configured for s in self._stub_array)


class nof_5qi_1_drb_configured_ge(CuCpCriteria):
    """5QI-1 DRBs"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_5qi_1_drb_configured for s in self._stub_array)


class nof_5qi_2_drb_configured_ge(CuCpCriteria):
    """5QI-2 DRBs"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).cu_cp.nof_5qi_2_drb_configured for s in self._stub_array)
