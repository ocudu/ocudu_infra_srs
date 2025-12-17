#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Viavi KPIs and procedure failures
"""

import logging
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ViaviProcedureFailure:
    """
    Viavi Failure
    """

    procedure_group: str
    procedure_name: str
    nof_failure: int


@dataclass
# pylint: disable=too-many-instance-attributes
class ViaviLinkData:
    """
    Viavi Link Data
    """

    ber: Optional[float]
    bler: Optional[float]
    num_tbs: Optional[int]
    num_tbs_errors: Optional[int]
    num_tbs_ack: Optional[int]
    num_tbs_nack: Optional[int]
    num_tbs_newly_transmitted: Optional[int]
    num_tbs_repeated: Optional[int]
    num_tbs_retransmitted: Optional[int]
    num_bits: Optional[int]
    num_bits_ack: Optional[int]
    total_bits: Optional[int]
    total_bits_errors: Optional[int]


class ViaviKPIs:
    """
    Viavi KPIs and procedure failures
    """

    def __init__(
        self,
        failures: List[ViaviProcedureFailure],
        dl_data: ViaviLinkData,
        ul_data: ViaviLinkData,
        warning_array: List[str],
    ):
        self._failures = failures
        self.dl_data = dl_data
        self.ul_data = ul_data
        self.warning_array = warning_array

    def print_procedure_failures(self, omit_failure_list: List[str]):
        """
        Print failures
        """
        for failure in self._filer_procedure_failure_list(self._failures, omit_failure_list):
            logging.error(
                "Procedure Group: %s, Procedure Name: %s, No of Failures: %s",
                failure.procedure_group,
                failure.procedure_name,
                failure.nof_failure,
            )

    def get_number_of_procedure_failures(self, omit_failure_list: List[str]) -> int:
        """
        Get number of failures
        """
        return len(self._get_procedure_failure_list(omit_failure_list))

    def _get_procedure_failure_list(self, omit_failure_list: List[str]) -> List[ViaviProcedureFailure]:
        return self._filer_procedure_failure_list(self._failures, omit_failure_list)

    @staticmethod
    def _filer_procedure_failure_list(
        failure_list: List[ViaviProcedureFailure], omit_failure_list: List[str]
    ) -> List[ViaviProcedureFailure]:
        """
        Filter out failures listed in omit_failure_list
        """
        return [failure for failure in failure_list if failure.procedure_name not in omit_failure_list]

    def get_nof_procedure_failure_by_group(self, group: str, procedure: str) -> Optional[int]:
        """
        Get nof failure by group and procedure
        """
        for failure in self._failures:
            if failure.procedure_group == group and failure.procedure_name == procedure:
                return failure.nof_failure
        return None
