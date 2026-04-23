# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Viavi pass/fail criteria definitions.
"""

import operator

from retina.launcher.criteria import ViaviCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class viavi_nof_ko_dl(ViaviCriteria):
    """DL KOs (viavi)"""

    operator_method = operator.le

    def callback(self):
        return self._stub_array.get_test_kpis().dl_data.num_tbs_errors


class viavi_nof_ko_ul(ViaviCriteria):
    """UL KOs (viavi)"""

    operator_method = operator.le

    def callback(self):
        return self._stub_array.get_test_kpis().ul_data.num_tbs_nack


class viavi_warnings(ViaviCriteria):
    """Viavi Warnings"""

    operator_method = operator.lt

    def callback(self):
        return len(self._stub_array.get_test_kpis().warning_array)


class viavi_procedure_table(ViaviCriteria):
    """Procedure table"""

    operator_method = operator.eq

    def callback(self):
        return self._stub_array.get_test_kpis().get_number_of_procedure_failures(["authentication"])
