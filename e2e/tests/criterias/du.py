# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
DU pass/fail criteria definitions
"""

import operator
from statistics import mean

from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.launcher.criteria import DuCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class dl_bitrate_gt(DuCriteria):
    """DL Bitrate"""

    operator_method = operator.gt

    def callback(self):
        return mean(s.GetMetrics(Empty()).aggregate.dl_bitrate for s in self._stub_array)


class ul_bitrate_gt(DuCriteria):
    """UL Bitrate"""

    operator_method = operator.gt

    def callback(self):
        return mean(s.GetMetrics(Empty()).aggregate.ul_bitrate for s in self._stub_array)


class nof_ko_dl_le(DuCriteria):
    """DL KOs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_ko_dl for s in self._stub_array)


class nof_ko_ul_le(DuCriteria):
    """UL KOs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_ko_ul for s in self._stub_array)


class max_late_dl_harqs_le(DuCriteria):
    """Late DL HARQs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.max_late_dl_harqs for s in self._stub_array)


class max_late_ul_harqs_le(DuCriteria):
    """Late UL HARQs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.max_late_ul_harqs for s in self._stub_array)


class nof_error_indications_le(DuCriteria):
    """Error indications"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_error_indications for s in self._stub_array)


class nof_pucch_f0f1_invalid_harqs_le(DuCriteria):
    """PUCCH f0/f1 invalid HARQs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_pucch_f0f1_invalid_harqs for s in self._stub_array)


class nof_pucch_f2f3f4_invalid_harqs_le(DuCriteria):
    """PUCCH f2/f3/f4 invalid HARQs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_pucch_f2f3f4_invalid_harqs for s in self._stub_array)


class nof_pucch_f2f3f4_invalid_csis_le(DuCriteria):
    """PUCCH f2/f3/f4 invalid CSIs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_pucch_f2f3f4_invalid_csis for s in self._stub_array)


class nof_pusch_invalid_csis_le(DuCriteria):
    """PUSCH invalid CSIs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_pusch_invalid_csis for s in self._stub_array)


class nof_pusch_invalid_harqs_le(DuCriteria):
    """PUSCH invalid HARQs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_pusch_invalid_harqs for s in self._stub_array)


class nof_reestablishments_eq(DuCriteria):
    """Reestablishments"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_reestablishments_complete for s in self._stub_array)


class nof_reestablishments_ge(DuCriteria):
    """Reestablishments"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_reestablishments_complete for s in self._stub_array)


class nof_handovers_eq(DuCriteria):
    """Handovers"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_handovers for s in self._stub_array)


class nof_handovers_ge(DuCriteria):
    """Handovers"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_handovers for s in self._stub_array)


class errors_le(DuCriteria):
    """Errors"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.Stop.with_call(UInt32Value(value=15), timeout=15)[0].error_count for s in self._stub_array)


class warnings_le(DuCriteria):
    """Warnings"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.Stop.with_call(UInt32Value(value=15), timeout=15)[0].warning_count for s in self._stub_array)


class prach_configuration_index_eq(DuCriteria):
    """PRACH Config Index"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.prach_configuration_index for s in self._stub_array)


class transform_precoder_eq(DuCriteria):
    """Transform Precoder"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.transform_precoder for s in self._stub_array)


class c_srs_eq(DuCriteria):
    """c-SRS"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.c_srs for s in self._stub_array)


class b_srs_eq(DuCriteria):
    """b-SRS"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.b_srs for s in self._stub_array)


class t312_eq(DuCriteria):
    """T312"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.t312 for s in self._stub_array)


class drx_long_cycle_eq(DuCriteria):
    """DRX Long Cycle"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.drx_long_cycle_start_offset for s in self._stub_array)


class nof_paging_eq(DuCriteria):
    """Paging messages"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_paging_messages for s in self._stub_array)


class nof_rrc_resume_request_eq(DuCriteria):
    """RRC Resume Request"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_rrc_resume_request for s in self._stub_array)


class nof_rrc_resume_request_ge(DuCriteria):
    """RRC Resume Request"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_rrc_resume_request for s in self._stub_array)


class nof_rrc_suspend_eq(DuCriteria):
    """RRC Suspend (suspendConfig)"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_rrc_suspend for s in self._stub_array)


class nof_rrc_suspend_ge(DuCriteria):
    """RRC Suspend (suspendConfig)"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_rrc_suspend for s in self._stub_array)


class nof_sib1_ge(DuCriteria):
    """SIB1 transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib1_transmissions for s in self._stub_array)


class nof_sib2_ge(DuCriteria):
    """SIB2 transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib2_transmissions for s in self._stub_array)


class nof_sib3_ge(DuCriteria):
    """SIB3 transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib3_transmissions for s in self._stub_array)


class nof_sib4_ge(DuCriteria):
    """SIB4 transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib4_transmissions for s in self._stub_array)


class nof_sib5_ge(DuCriteria):
    """SIB5 transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib5_transmissions for s in self._stub_array)


class nof_sib8_ge(DuCriteria):
    """SIB8 transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib8_transmissions for s in self._stub_array)


class sib1_has_rach_prioritization_slice_eq(DuCriteria):
    """RACH prioritization for slicing present in SIB1"""

    operator_method = operator.eq

    def callback(self) -> bool:
        return any(s.GetMetrics(Empty()).du.sib1_has_rach_prioritization_slice for s in self._stub_array)


class nof_sib16_ge(DuCriteria):
    """SIB16 transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib16_transmissions for s in self._stub_array)


class nof_sib19_ge(DuCriteria):
    """SIB19 transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib19_transmissions for s in self._stub_array)


class dl_max_mcs_ge(DuCriteria):
    """DL max MCS"""

    operator_method = operator.ge

    def callback(self) -> int:
        return max((s.GetMetrics(Empty()).aggregate.dl_max_mcs for s in self._stub_array), default=0)


class ul_max_mcs_ge(DuCriteria):
    """UL max MCS"""

    operator_method = operator.ge

    def callback(self) -> int:
        return max((s.GetMetrics(Empty()).aggregate.ul_max_mcs for s in self._stub_array), default=0)


class dl_avg_ri_ge(DuCriteria):
    """DL avg RI"""

    operator_method = operator.ge

    def callback(self):
        return mean(s.GetMetrics(Empty()).aggregate.dl_avg_ri for s in self._stub_array)


class ul_avg_ri_ge(DuCriteria):
    """UL avg RI"""

    operator_method = operator.ge

    def callback(self):
        return mean(s.GetMetrics(Empty()).aggregate.ul_avg_ri for s in self._stub_array)


class dl_ue_avg_bitrate(DuCriteria):
    """DL UE average bitrate"""

    @property
    def expected(self):
        return True

    def callback(self):
        du = self._stub_array[0]
        ues_tput = [ue.dl_av_30_samples for ue in du.GetMetrics(Empty()).ue_array]
        expected_tput = [item["value"] for item in self._input]
        return all(a > b for a, b in zip(ues_tput, expected_tput))


class ul_ue_avg_bitrate(DuCriteria):
    """UL UE average bitrate"""

    @property
    def expected(self):
        return True

    def callback(self):
        du = self._stub_array[0]
        ues_tput = [ue.ul_av_30_samples for ue in du.GetMetrics(Empty()).ue_array]
        expected_tput = [item["value"] for item in self._input]
        return all(a > b for a, b in zip(ues_tput, expected_tput))


class pdsch_prbs_used_per_tdd_slot_mean(DuCriteria):
    """PDSCH PRBs used per TDD slot index"""

    operator_method = operator.ge

    def callback(self):
        du = self._stub_array[0]
        return round(mean(du.GetMetrics(Empty()).du.pdsch_prbs_used_per_tdd_slot_idx), 1)


class pusch_prbs_used_per_tdd_slot_mean(DuCriteria):
    """PUSCH PRBs used per TDD slot index"""

    operator_method = operator.ge

    def callback(self):
        du = self._stub_array[0]
        return round(mean(du.GetMetrics(Empty()).du.pusch_prbs_used_per_tdd_slot_idx), 1)
