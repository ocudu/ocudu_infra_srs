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

from retina.protocol import CUCPClient, CUUPClient, DUClient, FiveGCClient, UEClient
from retina.viavi.client import Viavi

_UNSET = object()

_OPERATOR_SYMBOLS: Dict[Callable[..., bool], str] = {
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
    if isinstance(value, (tuple, list)):
        return "[" + ", ".join(map(_number_to_str, value)) + "]"
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

    def __init__(self, table: "CriteriaTable", stub_array: Any) -> None:
        self._stub_array = stub_array
        self._table = table
        self._input: Any = None
        self.__result: Any = _UNSET
        self._table.register(self)

    @final
    @property
    def criteria_id(self) -> str:
        """Unique criteria ID derived from the class qualified name."""
        return type(self).__module__.rsplit(".", maxsplit=1)[-1] + "." + type(self).__qualname__

    @final
    @property
    def name(self) -> str:
        """Human-readable name derived from the class docstring."""
        return type(self).__doc__ or ""

    operator_method: ClassVar[Callable[..., bool]] = operator.eq

    @property
    def expected(self) -> Any:
        """Expected value for comparison, derived from the configured input."""
        return self._input

    @property
    def expected_str(self) -> str:
        """Formatted string representation of the expected value with its operator symbol."""
        operator_symbol = _OPERATOR_SYMBOLS.get(
            self.operator_method, self.operator_method.__doc__ if self.operator_method.__doc__ else "?"
        )
        return f"{operator_symbol} {_number_to_str(self.expected)}"

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
        op: Callable[..., bool] = getattr(type(self), "operator_method")
        return bool(op(self.result, self.expected))

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


class UeCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for UE pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []
    _stub_array: Sequence[UEClient]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        UeCriteria.subclasses.append(cls)


class CuCpCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for CU-CP pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []
    _stub_array: Sequence[CUCPClient]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        CuCpCriteria.subclasses.append(cls)


class CuUpCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for CU-UP pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []
    _stub_array: Sequence[CUUPClient]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        CuUpCriteria.subclasses.append(cls)


class CuCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for CU criteria that aggregate across cu_cp and cu_up."""

    subclasses: ClassVar[List[type]] = []

    def __init__(self, table: "CriteriaTable") -> None:
        super().__init__(table, ())

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        CuCriteria.subclasses.append(cls)

    def callback(self) -> Any:
        name = type(self).__qualname__
        for cid, c in self._table._criteria.items():  # pylint: disable=protected-access
            if any(cid == f"{p}.{name}" for p in ("cu_cp", "cu_up")):
                return c.result
        raise ValueError(f"No cu_cp or cu_up criteria registered for {name!r}")


class DuCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for DU/gNB pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []
    _stub_array: Sequence[DUClient]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        DuCriteria.subclasses.append(cls)


class GnbCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for gNB criteria that aggregate across cu_cp, cu_up, and du."""

    subclasses: ClassVar[List[type]] = []

    def __init__(self, table: "CriteriaTable") -> None:
        super().__init__(table, ())

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        GnbCriteria.subclasses.append(cls)

    def callback(self) -> Any:
        name = type(self).__qualname__
        for cid, c in self._table._criteria.items():  # pylint: disable=protected-access
            if any(cid == f"{p}.{name}" for p in ("cu_cp", "cu_up", "du")):
                return c.result
        raise ValueError(f"No cu_cp, cu_up or du criteria registered for {name!r}")


class FiveGcCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for 5GC pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []
    _stub_array: Sequence[FiveGCClient]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        FiveGcCriteria.subclasses.append(cls)


class ViaviCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for Viavi pass/fail criteria definitions."""

    subclasses: ClassVar[List[type]] = []
    _stub_array: Viavi

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        ViaviCriteria.subclasses.append(cls)


class AllCriteria(Criteria):  # pylint: disable=too-few-public-methods
    """Base class for criteria that aggregate across all registered component criteria with the same name."""

    subclasses: ClassVar[List[type]] = []

    def __init__(self, table: "CriteriaTable") -> None:
        super().__init__(table, ())

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        AllCriteria.subclasses.append(cls)

    def callback(self) -> Any:
        results = []
        seen_stubs: set = set()
        for cid, c in self._table._criteria.items():  # pylint: disable=protected-access
            if not c._stub_array:  # pylint: disable=protected-access
                continue
            if not cid.endswith("." + type(self).__qualname__):
                continue
            stub_key = id(c._stub_array)  # pylint: disable=protected-access
            if stub_key not in seen_stubs:
                seen_stubs.add(stub_key)
                results.append(c.result)
        return self.all_callback(results)

    @abstractmethod
    def all_callback(self, result_array: Sequence[Any]) -> Any:
        """Function than receives the result of all criteria with the same criteria_id and generate the all result"""
