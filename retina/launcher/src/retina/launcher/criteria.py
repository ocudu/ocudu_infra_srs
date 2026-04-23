# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Pass/fail criteria management for test validation.
"""

import logging
import operator
import sys
from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, Dict, final, List, Sequence

import pytest
from rich.console import Console
from rich.table import Table

_UNSET = object()

_OPERATOR_SYMBOLS = {
    operator.lt: "<",
    operator.le: "<=",
    operator.eq: "==",
    operator.ne: "!=",
    operator.gt: ">",
    operator.ge: ">=",
}


def _number_to_str(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if not isinstance(value, (int, float)):
        return str(value)
    if value in (float("inf"), float("-inf")):
        return "∞" if value > 0 else "-∞"
    for threshold, suffix in ((1_000_000_000, "G"), (1_000_000, "M"), (1_000, "K")):
        if value >= threshold:
            return f"{value / threshold:.1f}{suffix}"
    return f"{value:.1f}"


class Criteria(ABC):  # pylint: disable=too-few-public-methods
    """Base class for pass/fail criteria definitions."""

    def __init__(self, table: "CriteriaTable", stub_array: Sequence) -> None:
        self._stub_array = stub_array
        self._input: Any = None
        self.__result: Any = _UNSET
        table.register(self)

    @final
    @property
    def criteria_id(self) -> str:
        """Unique criteria ID derived from the class qualified name."""
        return type(self).__qualname__

    @final
    @property
    def name(self) -> str:
        """Human-readable name derived from the class docstring."""
        return type(self).__doc__ or ""

    @property
    def operator_method(self) -> Callable:
        """Comparison operator; defaults to eq. Override as a class attribute."""
        return operator.eq

    @property
    def expected(self) -> Any:
        """Expected value for comparison, derived from the configured input."""
        return self._input

    @property
    def expected_str(self) -> str:
        """Formatted string representation of the expected value with its operator symbol."""
        return f"{_OPERATOR_SYMBOLS.get(self.operator_method, '?')} {_number_to_str(self.expected)}"

    @final
    @property
    def result(self) -> Any:
        """Lazily computed and cached result of callback()."""
        if self.__result is _UNSET:
            self.__result = self.callback()
        return self.__result

    @final
    def configure(self, config: Any) -> None:
        """Store the input config passed via CriteriaTable.add_criteria."""
        self._input = config

    @final
    def is_ok(self) -> bool:
        """Return True if result satisfies operator_method(result, expected)."""
        return self.operator_method(self.result, self.expected)

    @abstractmethod
    def callback(self) -> Any:
        """Compute the result using self._array and optionally self._input."""


class CriteriaTable:
    """Manage and validate test pass/fail criteria."""

    def __init__(self, capsys: pytest.CaptureFixture[str]):
        self._criteria: Dict[str, Criteria] = {}
        self._order: List[str] = []
        self._capsys = capsys

    def register(self, criteria: Criteria) -> None:
        """Register a Criteria instance; called automatically from Criteria.__init__."""
        if criteria.criteria_id in self._criteria:
            raise ValueError(f"{criteria.criteria_id} criteria already registered")
        self._criteria[criteria.criteria_id] = criteria

    def add_criteria(self, criteria_id: str, config: Any) -> None:
        """Activate a registered criteria by supplying its expected input config."""
        if criteria_id not in self._criteria:
            raise KeyError(f"{criteria_id} not registered")
        self._criteria[criteria_id].configure(config)
        self._order.append(criteria_id)

    def validate(self) -> None:
        """Build and log the pass/fail results table, failing the test if any criteria failed."""
        table = Table(title="Pass/Fail Criteria")
        table.add_column("Criteria Name", justify="left", style="cyan", no_wrap=True)
        table.add_column("Result", justify="right", style="magenta")
        table.add_column("Expected", justify="right", style="magenta")
        table.add_column("Pass", justify="center", style="magenta")

        failures = []
        for criteria_id in self._order:
            c = self._criteria[criteria_id]
            ok = c.is_ok()
            table.add_row(
                c.name,
                _number_to_str(c.result),
                c.expected_str,
                "✅" if ok else "❌",
                style="green" if ok else "red",
            )
            if not ok:
                failures.append(c.name)

        console = Console()
        with console.capture() as capture:
            console.print(table)
        with self._capsys.disabled():
            logging.info("\n%s", capture.get())

        if sys.exc_info()[0] is None and failures:
            pytest.fail("Test didn't pass the following criteria: " + ", ".join(failures))


class DuCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for DU/gNB pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        DuCriteria.subclasses.append(cls)


class FiveGcCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for 5GC pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        FiveGcCriteria.subclasses.append(cls)


class ViaviCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for Viavi pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        ViaviCriteria.subclasses.append(cls)
