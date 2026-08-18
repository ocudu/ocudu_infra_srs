# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
DU pass/fail criteria definitions
"""

import operator
from statistics import mean
from typing import List

from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.launcher.criteria import DuCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class dl_bitrate_gt(DuCriteria):
    """DL Bitrate"""

    operator_method = operator.gt

    def callback(self) -> float:
        return float(mean(s.GetMetrics(Empty()).aggregate.dl_bitrate for s in self._stub_array))


class ul_bitrate_gt(DuCriteria):
    """UL Bitrate"""

    operator_method = operator.gt

    def callback(self) -> float:
        return float(mean(s.GetMetrics(Empty()).aggregate.ul_bitrate for s in self._stub_array))


class nof_ko_dl_le(DuCriteria):
    """DU DL KOs"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_ko_dl for s in self._stub_array)


class nof_ko_ul_le(DuCriteria):
    """DU UL KOs"""

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
    """Error Indications"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_error_indications for s in self._stub_array)


class nof_conres_issues_eq(DuCriteria):
    """Contention Resolution Issues"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_conres_issues for s in self._stub_array)


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


class nof_reestablishments_request_eq(DuCriteria):
    """Reestablishment requests"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_reestablishments_request for s in self._stub_array)


class nof_reestablishments_request_le(DuCriteria):
    """Reestablishment requests"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_reestablishments_request for s in self._stub_array)


class nof_reestablishments_complete_eq(DuCriteria):
    """Reestablishment completions"""

    operator_method = operator.eq

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


class total_prach_preambles_eq(DuCriteria):
    """PRACH Preambles"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.total_prach_preambles for s in self._stub_array)


class two_step_prachs_detected_eq(DuCriteria):
    """2-step PRACH Preambles"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.two_step_prachs_detected for s in self._stub_array)


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


# b-SRS supported in retina but no criterion used in any test


class t312_eq(DuCriteria):
    """T312 Duration Enum"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.t312 for s in self._stub_array)


class drx_long_cycle_eq(DuCriteria):
    """DRX Long Cycle"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.drx_long_cycle_start_offset for s in self._stub_array)


class nof_paging_eq(DuCriteria):
    """Paging Messages"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_paging_messages for s in self._stub_array)


class nof_paging_ge(DuCriteria):
    """Paging Messages"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_paging_messages for s in self._stub_array)


class nof_rrc_suspend_eq(DuCriteria):
    """RRC Suspend"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_rrc_suspend for s in self._stub_array)


class nof_rrc_resume_complete_eq(DuCriteria):
    """RRC Resume Complete"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).aggregate.nof_rrc_resume_complete for s in self._stub_array)


class nof_sib1_ge(DuCriteria):
    """SIB1 Transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib1_transmissions for s in self._stub_array)


class nof_sib2_ge(DuCriteria):
    """SIB2 Transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib2_transmissions for s in self._stub_array)


class nof_sib3_ge(DuCriteria):
    """SIB3 Transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib3_transmissions for s in self._stub_array)


class nof_sib4_ge(DuCriteria):
    """SIB4 Transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib4_transmissions for s in self._stub_array)


# nof_sib5_transmissions supported in retina but not used in any test criterion


class nof_sib6_ge(DuCriteria):
    """SIB6 (ETWS primary notification) Transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib6_transmissions for s in self._stub_array)


class nof_sib7_ge(DuCriteria):
    """SIB7 (ETWS secondary notification) Transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib7_transmissions for s in self._stub_array)


class nof_sib8_ge(DuCriteria):
    """SIB8 (CMAS) Transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib8_transmissions for s in self._stub_array)


class sib1_has_rach_prioritization_slice_eq(DuCriteria):
    """SIB1 RACH Prioritization Slice"""

    operator_method = operator.eq

    def callback(self) -> bool:
        return any(s.GetMetrics(Empty()).du.sib1_has_rach_prioritization_slice for s in self._stub_array)


class nof_sib16_ge(DuCriteria):
    """SIB16 Transmissions"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_sib16_transmissions for s in self._stub_array)


# nof_sib19_transmissions supported in retina but not used in any test criterion


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

    def callback(self) -> float:
        return float(mean(s.GetMetrics(Empty()).aggregate.dl_avg_ri for s in self._stub_array))


class ul_avg_ri_ge(DuCriteria):
    """UL avg RI"""

    operator_method = operator.ge

    def callback(self) -> float:
        return float(mean(s.GetMetrics(Empty()).aggregate.ul_avg_ri for s in self._stub_array))


def _all_gt(result: List[float], expected: List[float]) -> bool:
    ">"
    return all(a > b for a, b in zip(result, expected))


def _all_lt(result: List[float], expected) -> bool:
    "<"
    exp = expected if isinstance(expected, list) else [expected] * len(result)
    return all(a < b for a, b in zip(result, exp))


class dl_ue_mid10_bitrate(DuCriteria):
    """DL UE mid-10 bitrate"""

    operator_method = _all_gt

    @property
    def expected(self):
        return [item["value"] for item in self._input]

    def callback(self) -> List[float]:
        du = self._stub_array[0]
        return [ue.dl_av_mid10_samples for ue in du.GetMetrics(Empty()).ue_array]


class ul_ue_mid10_bitrate(DuCriteria):
    """UL UE mid-10 bitrate"""

    operator_method = _all_gt

    @property
    def expected(self):
        return [item["value"] for item in self._input]

    def callback(self) -> List[float]:
        du = self._stub_array[0]
        return [ue.ul_av_mid10_samples for ue in du.GetMetrics(Empty()).ue_array]


# pdsch_prbs_used_per_tdd_slot_idx supported in retina but not used in any test criterion
# pusch_prbs_used_per_tdd_slot_mean supported in retina but not used in any test criterion


class pdsch_prbs_mid10_per_tdd_slot_mean(DuCriteria):
    """PDSCH PRBs per TDD slot (mid 10)"""

    operator_method = operator.ge

    def callback(self) -> float:
        du = self._stub_array[0]
        return float(round(mean(du.GetMetrics(Empty()).du.pdsch_prbs_mid10_per_tdd_slot_idx), 1))


class pusch_prbs_mid10_per_tdd_slot_mean(DuCriteria):
    """PUSCH PRBs per TDD slot (mid 10)"""

    operator_method = operator.ge

    def callback(self) -> float:
        du = self._stub_array[0]
        return float(round(mean(du.GetMetrics(Empty()).du.pusch_prbs_mid10_per_tdd_slot_idx), 1))


class ue_bsr_max_le(DuCriteria):
    """UE BSR MAX less than"""

    operator_method = _all_lt

    def callback(self):
        du = self._stub_array[0]
        return [ue.bsr_max for ue in du.GetMetrics(Empty()).ue_array]


class nof_cg_type1_eq(DuCriteria):
    """Configured Grant Type 1 setups"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_cg_type1 for s in self._stub_array)


class nof_cg_type2_eq(DuCriteria):
    """Configured Grant Type 2 setups"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_cg_type2 for s in self._stub_array)


class nof_cs_rnti_eq(DuCriteria):
    """CS-RNTI setups"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_cs_rnti for s in self._stub_array)


class nof_rlm_ssb_resources_ge(DuCriteria):
    """RLM SSB Resources"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_rlm_ssb_resources for s in self._stub_array)


class nof_rlm_ssb_resources_eq(DuCriteria):
    """RLM SSB Resources"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_rlm_ssb_resources for s in self._stub_array)


class nof_rlm_csi_rs_resources_ge(DuCriteria):
    """RLM CSI-RS Resources"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_rlm_csi_rs_resources for s in self._stub_array)


class nof_rlm_csi_rs_resources_eq(DuCriteria):
    """RLM CSI-RS Resources"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_rlm_csi_rs_resources for s in self._stub_array)
