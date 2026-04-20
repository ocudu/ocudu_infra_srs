# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

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


def run_analyzers(pcap_file: str, analyzers: Sequence[PcapAnalyzer], tshark_param: str = "") -> Metrics:
    """
    Runs all analyzers against *pcap_file*.  Analyzers that share the same
    display_filter are batched into a single tshark process.  *tshark_param* is
    passed verbatim to every tshark invocation (e.g. "--enable-heuristic rlc_nr_udp").

    Calls `report()` on every analyzer when the loop ends, regardless of reason.
    """

    if Path(pcap_file).exists():
        logging.info("[Pcap Parsing] %s", pcap_file)

        analyzers_grouped: Dict[str, List[PcapAnalyzer]] = {}
        for a in analyzers:
            if a.display_filter not in analyzers_grouped:
                analyzers_grouped[a.display_filter] = []
            analyzers_grouped[a.display_filter].append(a)

        for display_filter, analyzers_with_same_filter in analyzers_grouped.items():
            try:
                with pyshark.FileCapture(
                    pcap_file,
                    keep_packets=False,
                    display_filter=display_filter,
                    custom_parameters=tshark_param.split() if tshark_param else [],
                ) as capture:
                    for packet in capture:
                        for analyzer in analyzers_with_same_filter:
                            try:
                                analyzer.process(packet)
                            except Exception:  # pylint: disable=broad-except
                                logging.exception("Error in %s while processing packet", type(analyzer).__name__)
            except Exception as err:  # pylint: disable=broad-except
                logging.warning("[Pcap Parsing] TShark failed on %s for filter %s: %s", pcap_file, display_filter, err)

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
    parser.add_argument("--tshark-param", help="Tshark Parameters", required=False, default="")
    args = parser.parse_args()

    instances = []
    for analyzer_name in args.analyzers:
        try:
            instances.append(_load_analyzer(analyzer_name))
        except (ValueError, ImportError, AttributeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    results = run_analyzers(args.pcap_file, instances, args.tshark_param)
    logging.info("%s", MessageToString(results, as_one_line=True))


if __name__ == "__main__":
    _main()
