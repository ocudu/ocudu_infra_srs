# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
DU/gNB pass/fail criteria definitions
"""

import operator
from statistics import mean

from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.launcher.criteria import DuCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class dl_bitrate(DuCriteria):
    """DL Bitrate"""

    operator_method = operator.gt

    def callback(self):
        return mean(s.GetMetrics(Empty()).dl_bitrate for s in self._stub_array)


class ul_bitrate(DuCriteria):
    """UL Bitrate"""

    operator_method = operator.gt

    def callback(self):
        return mean(s.GetMetrics(Empty()).ul_bitrate for s in self._stub_array)


class nof_ko_dl(DuCriteria):
    """DL KOs"""

    operator_method = operator.le

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_ko_dl for s in self._stub_array)


class nof_ko_ul(DuCriteria):
    """UL KOs"""

    operator_method = operator.le

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_ko_ul for s in self._stub_array)


class max_late_dl_harqs(DuCriteria):
    """Late DL HARQs"""

    operator_method = operator.le

    def callback(self):
        return sum(s.GetMetrics(Empty()).max_late_dl_harqs for s in self._stub_array)


class max_late_ul_harqs(DuCriteria):
    """Late UL HARQs"""

    operator_method = operator.le

    def callback(self):
        return sum(s.GetMetrics(Empty()).max_late_ul_harqs for s in self._stub_array)


class nof_error_indications(DuCriteria):
    """Error indications"""

    operator_method = operator.le

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_error_indications for s in self._stub_array)


class nof_pucch_f0f1_invalid_harqs(DuCriteria):
    """PUCCH f0/f1 HARQs"""

    operator_method = operator.le

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_pucch_f0f1_invalid_harqs for s in self._stub_array)


class nof_reestablishments_eq(DuCriteria):
    """Reestablishments"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_reestablishments_complete for s in self._stub_array)


class nof_reestablishments_ge(DuCriteria):
    """Reestablishments"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_reestablishments_complete for s in self._stub_array)


class nof_handovers_eq(DuCriteria):
    """Handovers"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_handovers for s in self._stub_array)


class nof_handovers_ge(DuCriteria):
    """Handovers"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_handovers for s in self._stub_array)


class errors(DuCriteria):
    """Errors"""

    operator_method = operator.le

    def callback(self):
        return sum(s.Stop.with_call(UInt32Value(value=15), timeout=15)[0].error_count for s in self._stub_array)


class warnings(DuCriteria):
    """Warnings"""

    operator_method = operator.le

    def callback(self):
        return sum(s.Stop.with_call(UInt32Value(value=15), timeout=15)[0].warning_count for s in self._stub_array)


class prach_configuration_index_eq(DuCriteria):
    """PRACH Config Index"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).prach_configuration_index for s in self._stub_array)


class transform_precoder_eq(DuCriteria):
    """Transform Precoder"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).transform_precoder for s in self._stub_array)


class c_srs_eq(DuCriteria):
    """c-SRS"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).c_srs for s in self._stub_array)


class b_srs_eq(DuCriteria):
    """b-SRS"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).b_srs for s in self._stub_array)


class t312_eq(DuCriteria):
    """T312"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).t312 for s in self._stub_array)


class drx_long_cycle_eq(DuCriteria):
    """DRX Long Cycle"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).drx_long_cycle_start_offset for s in self._stub_array)


class nof_paging_eq(DuCriteria):
    """Paging messages"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_paging_messages for s in self._stub_array)


class nof_rrc_resume_request_eq(DuCriteria):
    """RRC Resume Request"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_rrc_resume_request for s in self._stub_array)


class nof_rrc_resume_request_geq(DuCriteria):
    """RRC Resume Request"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_rrc_resume_request for s in self._stub_array)


class nof_rrc_suspend_eq(DuCriteria):
    """RRC Suspend (suspendConfig)"""

    operator_method = operator.eq

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_rrc_suspend for s in self._stub_array)


class nof_rrc_suspend_geq(DuCriteria):
    """RRC Suspend (suspendConfig)"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_rrc_suspend for s in self._stub_array)


class nof_sib1_geq(DuCriteria):
    """SIB1 transmissions"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_sib1_transmissions for s in self._stub_array)


class nof_sib2_geq(DuCriteria):
    """SIB2 transmissions"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_sib2_transmissions for s in self._stub_array)


class nof_sib3_geq(DuCriteria):
    """SIB3 transmissions"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_sib3_transmissions for s in self._stub_array)


class nof_sib4_geq(DuCriteria):
    """SIB4 transmissions"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_sib4_transmissions for s in self._stub_array)


class nof_sib5_geq(DuCriteria):
    """SIB5 transmissions"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_sib5_transmissions for s in self._stub_array)


class nof_sib8_geq(DuCriteria):
    """SIB8 transmissions"""

    operator_method = operator.ge

    def callback(self):
        return sum(s.GetMetrics(Empty()).nof_sib8_transmissions for s in self._stub_array)


class dl_avg_ri_geq(DuCriteria):
    """DL avg RI"""

    operator_method = operator.ge

    def callback(self):
        return mean(s.GetMetrics(Empty()).dl_avg_ri for s in self._stub_array)


class ul_avg_ri_geq(DuCriteria):
    """UL avg RI"""

    operator_method = operator.ge

    def callback(self):
        return mean(s.GetMetrics(Empty()).ul_avg_ri for s in self._stub_array)
