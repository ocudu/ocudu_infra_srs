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
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pyshark
from google.protobuf.text_format import MessageToString
from retina.protocol.base_pb2 import Metrics


class PcapAnalyzer(ABC):
    """
    Base class for pcap packet analyzers.

    Subclass this, implement `process` and `report`, and optionally override `display_filter`.
    """

    @property
    def tshark_params(self) -> Tuple[str, ...]:
        """
        custom parameters for tshark
        """
        return ()

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
    def report(self) -> Metrics:
        """Called once when the capture ends. Return the analysis result."""


def run_analyzers(pcap_file: str, analyzers: Sequence[PcapAnalyzer]) -> Metrics:
    """
    All analyzer display filters are OR-combined into a single tshark filter so
    only one tshark process is spawned. Calls `report()` on every analyzer when
    the loop ends, regardless of reason.

    *dissector* selects the pcap format: "mac" for MAC-NR pcaps, "rlc" for RLC-NR
    pcaps (enables the rlc_nr_udp heuristic dissector in tshark).

    Returns a list of results in the same order as *analyzers*.
    """

    if Path(pcap_file).exists():
        logging.info("[Pcap Parsing] %s", pcap_file)

        analyzers_grouped: Dict[Tuple[str, ...], Dict[str, List[PcapAnalyzer]]] = {}
        for a in analyzers:
            if a.tshark_params not in analyzers_grouped:
                analyzers_grouped[a.tshark_params] = {}
            if a.display_filter not in analyzers_grouped[a.tshark_params]:
                analyzers_grouped[a.tshark_params][a.display_filter] = []
            analyzers_grouped[a.tshark_params][a.display_filter].append(a)

        for tshark_params, analyzer_by_filter in analyzers_grouped.items():
            for display_filter, analyzer_with_same_tshark_call in analyzer_by_filter.items():
                try:
                    with pyshark.FileCapture(
                        pcap_file,
                        keep_packets=False,
                        display_filter=display_filter,
                        custom_parameters=list(tshark_params),
                    ) as capture:
                        for packet in capture:
                            for analyzer in analyzer_with_same_tshark_call:
                                try:
                                    analyzer.process(packet)
                                except Exception:  # pylint: disable=broad-except
                                    logging.exception("Error in %s while processing packet", type(analyzer).__name__)
                except Exception as err:  # pylint: disable=broad-except
                    logging.exception(err)

    else:
        logging.warning("[Pcap Parsing] file not found: %s", pcap_file)

    result = Metrics()
    for analyzer in analyzers:
        report = analyzer.report()
        logging.info("[Pcap Parsing] %s Output: %s", type(analyzer).__name__, MessageToString(report, as_one_line=True))
        result.MergeFrom(report)

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
        "rlc.pcap rrc.HandoverAnalyzer rrc.ReestablishmentAnalyzer ",
    )
    parser.add_argument("pcap_file", help="Path to the pcap/pcapng file")
    parser.add_argument(
        "analyzers",
        nargs="+",
        metavar="module.ClassName",
        help='Analyzer specs relative to this package, e.g. "rrc.HandoverAnalyzer"',
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
    logging.info("%s", MessageToString(results, as_one_line=True))


if __name__ == "__main__":
    _main()
