# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Cross-component aggregate pass/fail criteria definitions.
"""

import operator
from typing import Any, Sequence

from retina.launcher.criteria import AllCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class errors_le(AllCriteria):
    """Errors"""

    operator_method = operator.le

    def all_callback(self, result_array: Sequence[Any]) -> Any:
        return sum(result_array)


class warnings_le(AllCriteria):
    """Warnings"""

    operator_method = operator.le

    def all_callback(self, result_array: Sequence[Any]) -> Any:
        return sum(result_array)
