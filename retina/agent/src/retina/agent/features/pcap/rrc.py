#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
5G NR RRC-layer pcap analyzers.
"""

from typing import Dict, Tuple


from retina.agent.features.pcap.analyzer import PcapAnalyzer


class HandoverAnalyzer(PcapAnalyzer):
    """
    Counts DL RRCReconfiguration messages carrying reconfigurationWithSync.

    Each such message corresponds to a handover command sent to a UE.
    tshark display filter: nr-rrc.reconfigurationWithSync_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def tshark_params(self) -> Tuple[str, ...]:
        return "--enable-heuristic", "rlc_nr_udp"

    @property
    def display_filter(self) -> str:
        return "nr-rrc.reconfigurationWithSync_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Dict[str, int]:
        return {"handover_count": self._count}


class ReestablishmentAnalyzer(PcapAnalyzer):
    """
    Counts RRC Reestablishment requests and completions.

    - Request:    UL CCCH RRCReestablishmentRequest  (nr-rrc.rrcReestablishmentRequest_element)
    - Completion: UL DCCH RRCReestablishmentComplete (nr-rrc.rrcReestablishmentComplete_element)

    A single tshark filter matches both; process() differentiates them by the
    presence of the reestablishmentCause field (only in requests).
    """

    def __init__(self) -> None:
        self._request_count = 0
        self._completion_count = 0

    @property
    def tshark_params(self) -> Tuple[str, ...]:
        return "--enable-heuristic", "rlc_nr_udp"

    @property
    def display_filter(self) -> str:
        return "nr-rrc.rrcReestablishmentRequest_element || nr-rrc.rrcReestablishmentComplete_element"

    def process(self, packet) -> None:
        cause_raw = getattr(packet, "nr-rrc", "reestablishmentcause")
        if cause_raw:
            # RRCReestablishmentRequest — reestablishmentCause is only present here
            self._request_count += 1
        else:
            # RRCReestablishmentComplete
            self._completion_count += 1

    def report(self) -> Dict[str, int]:
        return {
            "reestablishment_request_count": self._request_count,
            "reestablishment_complete_count": self._completion_count,
        }
