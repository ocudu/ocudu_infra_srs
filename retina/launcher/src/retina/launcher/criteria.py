#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Pass/fail criteria management for test validation.
"""

import logging
import operator
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pytest
from rich.console import Console
from rich.table import Table


@dataclass
class _CriteriaDefinition:
    name: str
    callback: Callable
    operator_method: Callable
    expected: Optional[float] = None
    _result: Optional[float] = None

    @property
    def expected_str(self) -> str:
        """Return formatted string representation of expected value with operator."""
        if self.expected is None:
            return "?"
        operator_str = {
            operator.lt: "<",
            operator.le: "<=",
            operator.eq: "==",
            operator.ne: "!=",
            operator.gt: ">",
            operator.ge: ">=",
        }.get(self.operator_method, "?")
        return f"{operator_str} {self._number_to_str(self.expected)}"

    @property
    def result(self) -> float:
        """Return the result value, computing it if not already cached."""
        if self._result is None:
            self._result = self.callback()
            if self._result is None:
                self._result = 0
        return self._result

    @property
    def result_str(self) -> str:
        """Return formatted string representation of the result value."""
        return self._number_to_str(self.result)

    def is_requested(self) -> bool:
        """Check if this criteria has been requested (has an expected value)."""
        return self.expected is not None

    def is_ok(self) -> bool:
        """Check if the result meets the expected criteria."""
        if self.expected is None:
            return False
        return self.operator_method(self.result, self.expected)

    @staticmethod
    def _number_to_str(value: float) -> str:
        if value == float("inf"):
            return "∞"
        if value == float("-inf"):
            return "-∞"
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.1f}G"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return f"{value:.1f}"


class Criteria:
    """Manage and validate test pass/fail criteria."""

    def __init__(self, capsys: pytest.CaptureFixture[str]):
        self._criteria_dict: Dict[str, _CriteriaDefinition] = {}
        self._criteria_order: List[str] = []
        self._capsys = capsys

    def register_available_criteria(self, criteria_id: str, name: str, callback: Callable, operator_method: Callable):
        """Register a new criteria that can be validated."""
        if criteria_id in self._criteria_dict:
            raise ValueError(f"{criteria_id} criteria already registered")
        self._criteria_dict[criteria_id] = _CriteriaDefinition(
            name=name, callback=callback, operator_method=operator_method
        )

    def add_criteria(self, criteria_id: str, expected_value: float):
        """Add pass/fail criteria with operator and expected value."""
        if criteria_id not in self._criteria_dict:
            raise KeyError(f"{criteria_id} not registered")
        self._criteria_dict[criteria_id].expected = expected_value
        self._criteria_order.append(criteria_id)

    def validate(self):
        """
        Create a table with the results
        """
        table = Table(title="Pass/Fail Criteria")

        table.add_column("Criteria Name", justify="left", style="cyan", no_wrap=True)
        table.add_column("Result", justify="right", style="magenta")
        table.add_column("Expected", justify="right", style="magenta")
        table.add_column("Pass", justify="center", style="magenta")

        failures = []
        for criteria_id in self._criteria_order:
            criteria = self._criteria_dict[criteria_id]
            if criteria.is_requested():  # It has been added
                row_style = "green" if criteria.is_ok() else "red"
                table.add_row(
                    criteria.name,
                    criteria.result_str,
                    criteria.expected_str,
                    "✅" if criteria.is_ok() else "❌",
                    style=row_style,
                )
                if not criteria.is_ok():
                    failures.append(criteria.name)

        console = Console()
        # Capture the table to print it in the console
        with console.capture() as capture:
            console.print(table)
        output = "\n" + capture.get()

        # Disable temporarily the capsys to print the table
        with self._capsys.disabled():
            logging.info(output)

        if sys.exc_info()[0] is None and failures:
            pytest.fail("Test didn't pass the following criteria: " + ", ".join(failures))
