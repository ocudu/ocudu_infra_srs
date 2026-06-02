# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
JSON metrics analysis logic.
"""

import argparse
import importlib
import json
import logging
import sys
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from typing import List, Optional

from google.protobuf.text_format import MessageToString
from retina.protocol.base_pb2 import Metrics


class MovingAverage:
    """Moving average queue for up to N samples."""

    def __init__(self, max_length: int) -> None:
        self._queue: "deque[float]" = deque(maxlen=max_length)

    def add(self, value: float) -> None:
        """Add a new element to the queue."""
        self._queue.append(value)

    def get_average(self, nof_average_samples: Optional[int] = None) -> float:
        """Return the average of the last N elements in the queue."""
        if nof_average_samples is None:
            nof_average_samples = self._queue.maxlen or 0
        elif nof_average_samples > (self._queue.maxlen or 0) or nof_average_samples < 0:
            raise ValueError("nof_average_samples is greater than the maximum length of the queue")
        if len(self._queue) == 0:
            return 0
        last_k_values = list(self._queue)[-nof_average_samples:]
        return sum(last_k_values) / len(last_k_values)

    def get_middle_average(self, nof_middle_samples: int) -> float:
        """Return the average of the N temporally middle samples."""
        if nof_middle_samples > (self._queue.maxlen or 0) or nof_middle_samples < 0:
            raise ValueError("nof_middle_samples is greater than the maximum length of the queue")
        if len(self._queue) == 0:
            return 0
        values = list(self._queue)
        n = len(values)
        if n <= nof_middle_samples:
            return sum(values) / n
        start = (n - nof_middle_samples) // 2
        middle = values[start : start + nof_middle_samples]
        return sum(middle) / len(middle)


class JsonMetricsAnalyzer(ABC):
    """
    Base class for JSON metrics record analyzers.

    Subclass this and implement `process` and `report`.
    """

    @abstractmethod
    def process(self, metric_info: dict) -> None:
        """Called for every record in the metrics file."""

    @abstractmethod
    def report(self) -> Metrics:
        """Called once when all records have been processed. Return the analysis result."""


def run_json_analyzers(json_file: str, analyzers: List[JsonMetricsAnalyzer]) -> Metrics:
    """
    Read a JSON metrics file and run analyzers over each record.

    The file is expected to be a JSON array of metric objects as written by
    the WebSocket listener. Calls `report()` on every analyzer when done,
    regardless of errors, and merges all results into a single Metrics object.
    """
    if Path(json_file).exists():
        logging.info("[JSON Metrics] %s", json_file)
        try:
            with open(json_file, "r", encoding="utf-8") as fd:
                records = json.load(fd)
            for record in records:
                for analyzer in analyzers:
                    try:
                        analyzer.process(record)
                    except Exception:  # pylint: disable=broad-except
                        logging.exception("Error in %s while processing record", type(analyzer).__name__)
        except (json.JSONDecodeError, OSError):
            logging.exception("[JSON Metrics] Failed to read %s", json_file)
    else:
        logging.warning("[JSON Metrics] file not found: %s", json_file)

    result = Metrics()
    for analyzer in analyzers:
        report = analyzer.report()
        logging.info("[JSON Metrics] %s Output: %s", type(analyzer).__name__, MessageToString(report, as_one_line=True))
        result.MergeFrom(report)

    return result


############################################
# Logic to call this file to run analyzers #
############################################
# pylint: disable=duplicate-code  # CLI boilerplate is intentionally parallel to pcap/analyzer.py


def _this_package() -> str:
    if __package__:
        return __package__

    path = Path(__file__).resolve().parent
    parts: list = []
    while (path / "__init__.py").exists():
        parts.append(path.name)
        path = path.parent

    root = str(path)
    if root not in sys.path:
        sys.path.insert(0, root)

    return ".".join(reversed(parts))


def _load_analyzer(spec: str) -> JsonMetricsAnalyzer:
    parts = spec.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid analyzer spec '{spec}': expected 'module.ClassName'")
    module_name, class_name = parts
    full_module = f"{_this_package()}.{module_name}"
    try:
        mod = importlib.import_module(full_module)
    except ImportError as exc:
        raise ImportError(f"Cannot import '{full_module}': {exc}") from exc
    cls = getattr(mod, class_name, None)
    if cls is None:
        raise AttributeError(f"'{class_name}' not found in '{full_module}'")
    return cls()


def _main():
    logging.basicConfig(
        format="%(asctime)s \x1b[32;20m[%(levelname)s]\x1b[0m %(message)s",
        level=logging.INFO,
    )
    parser = argparse.ArgumentParser(
        description="Run metrics analyzers on a metrics file and print results.",
        epilog="Example: python -m retina.agent.features.json_metrics.analyzer "
        "metrics.json du_metrics.DuMetricsAnalyzer",
    )
    parser.add_argument("json_file", help="Path to the metrics json file")
    parser.add_argument(
        "analyzers",
        nargs="+",
        metavar="module.ClassName",
        help='Analyzer specs relative to this package, e.g. "du_metrics.DuMetricsAnalyzer"',
    )
    args = parser.parse_args()

    instances = []
    for analyzer_name in args.analyzers:
        try:
            instances.append(_load_analyzer(analyzer_name))
        except (ValueError, ImportError, AttributeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    results = run_json_analyzers(args.json_file, instances)
    logging.info("%s", MessageToString(results, as_one_line=True))


if __name__ == "__main__":
    _main()
