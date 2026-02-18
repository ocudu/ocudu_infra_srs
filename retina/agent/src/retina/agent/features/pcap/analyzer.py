#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Pcap analysis logic.
"""

import argparse
import importlib
import json
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

import pyshark


class PcapAnalyzer(ABC):
    """
    Base class for pcap packet analyzers.

    Subclass this, implement `process` and `report`, and optionally override `display_filter`.
    """

    @property
    def display_filter(self) -> str:
        """
        display filter applied at the tshark level (most efficient).
        Return an empty string to receive all packets.
        """
        return ""

    @abstractmethod
    def process(self, packet) -> None:
        """Called for every packet that passes `display_filter`."""

    @abstractmethod
    def report(self) -> Dict[str, Any]:
        """Called once when the capture ends. Return the analysis result."""


def run_analyzers(pcap_file: str, analyzers: List[PcapAnalyzer]) -> Dict[str, Any]:
    """
    All analyzer display filters are OR-combined into a single tshark filter so
    only one tshark process is spawned. Calls `report()` on every analyzer when
    the loop ends, regardless of reason.

    Returns a list of results in the same order as *analyzers*.
    """

    if not Path(pcap_file).exists():
        logging.warning("[Pcap Parsing] file not found: %s", pcap_file)
        return {}

    analyzers_by_display_filter: Dict[str, List[PcapAnalyzer]] = {}
    for a in analyzers:
        if a.display_filter not in analyzers_by_display_filter:
            analyzers_by_display_filter[a.display_filter] = []
        analyzers_by_display_filter[a.display_filter].append(a)

    result = {}
    for display_filter, analyzer_array in analyzers_by_display_filter.items():
        logging.info(
            "[Pcap Parsing] %s [%s] with analyzers: %s",
            pcap_file,
            display_filter,
            ", ".join(type(a).__name__ for a in analyzer_array),
        )
        try:
            with pyshark.FileCapture(pcap_file, keep_packets=False, display_filter=display_filter) as capture:
                for packet in capture:
                    for analyzer in analyzer_array:
                        try:
                            analyzer.process(packet)
                        except Exception:  # pylint: disable=broad-except
                            logging.exception("Error in %s while processing packet", type(analyzer).__name__)
        except Exception as err:  # pylint: disable=broad-except
            logging.exception(err)
        finally:
            for analyzer in analyzer_array:
                report = analyzer.report()
                logging.info("[Pcap Parsing] Output: %s", str(report))
                result.update(report)

    return result


############################################
# Logic to call this file to run analyzers #
############################################


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


def _load_analyzer(spec: str) -> PcapAnalyzer:
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
        description="Run pcap analyzers on a capture file and print results.",
        epilog="Example: python -m retina.agent.features.pcap.analyzer "
        "mac.pcap mac.HandoverAnalyzer mac.ReestablishmentAnalyzer",
    )
    parser.add_argument("pcap_file", help="Path to the pcap/pcapng file")
    parser.add_argument(
        "analyzers",
        nargs="+",
        metavar="module.ClassName",
        help='Analyzer specs relative to this package, e.g. "mac.HandoverAnalyzer"',
    )
    args = parser.parse_args()

    instances = []
    for analyzer_name in args.analyzers:
        try:
            instances.append(_load_analyzer(analyzer_name))
        except (ValueError, ImportError, AttributeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    results = run_analyzers(args.pcap_file, instances)
    logging.info(json.dumps(results, indent=2))


if __name__ == "__main__":
    _main()
