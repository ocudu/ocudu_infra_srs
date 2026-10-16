# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
5G NR RLC-layer pcap analyzers.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

from retina.protocol.base_pb2 import DrbMetrics, Metrics

from retina.agent.features.pcap.analyzer import PcapAnalyzer

# Bearer type of a DRB in the RLC pcap framing, and the direction of an uplink PDU. Both are
# written by the capture itself, see PCAP_RLC_BEARER_TYPE_DRB in ocudu and the rlc-nr dissector.
_BEARER_TYPE_DRB = 5
_DIRECTION_UPLINK = 0
_DIRECTION_DOWNLINK = 1


def _rlc_layer(packet):
    """Return the layer that carries the rlc-nr fields."""
    for layer in packet.layers:
        if "bearer_id" in layer.field_names:
            return layer
    raise KeyError("No NR-RLC layer found in packet")


@dataclass
class _FlowTotals:
    """What one direction of one bearer carried, and the span it carried it in."""

    nof_bytes: int = 0
    first_timestamp: float = 0.0
    last_timestamp: float = 0.0

    def add(self, nof_bytes: int, timestamp: float) -> None:
        """Account for one PDU."""
        if not self.nof_bytes:
            self.first_timestamp = timestamp
        self.nof_bytes += nof_bytes
        self.last_timestamp = timestamp

    @property
    def bitrate(self) -> float:
        """Rate the bytes amount to, 0 unless at least two PDUs span some time."""
        span = self.last_timestamp - self.first_timestamp
        return self.nof_bytes * 8 / span if span > 0 else 0.0


class DrbTrafficAnalyzer(PcapAnalyzer):
    """
    Sums the RLC PDU payload each DRB carried, per direction, from an RLC capture.

    A test asserting on this tells apart a bearer that was merely set up from one that actually
    served traffic, which the DRB counters of the CU-CP cannot do on their own. Note that an AM
    bearer carries its status PDUs on the same bearer id, so a floor low enough to be cleared by
    control traffic alone proves nothing.
    tshark display filter: rlc-nr.bearer-type == 5
    """

    def __init__(self) -> None:
        # (DRB id, direction) -> what it carried
        self._flow_dict: Dict[Tuple[int, int], _FlowTotals] = {}

    @property
    def display_filter(self) -> str:
        return f"rlc-nr.bearer-type == {_BEARER_TYPE_DRB}"

    def process(self, packet) -> None:
        try:
            layer = _rlc_layer(packet)
            drb_id = int(layer.bearer_id)
            direction = int(layer.direction)
            nof_bytes = int(layer.pdu_length)
            timestamp = float(packet.sniff_timestamp)
        except (AttributeError, KeyError, ValueError):
            return

        self._flow_dict.setdefault((drb_id, direction), _FlowTotals()).add(nof_bytes, timestamp)

    def report(self) -> Metrics:
        # Merging metrics appends repeated fields, so this must stay the only analyzer filling
        # drb_array or the bearers would be reported twice.
        drb_id_array = sorted({drb_id for drb_id, _ in self._flow_dict})
        empty = _FlowTotals()
        return Metrics(
            drb_array=[
                DrbMetrics(
                    drb_id=drb_id,
                    dl_bytes=self._flow_dict.get((drb_id, _DIRECTION_DOWNLINK), empty).nof_bytes,
                    ul_bytes=self._flow_dict.get((drb_id, _DIRECTION_UPLINK), empty).nof_bytes,
                    dl_bitrate=self._flow_dict.get((drb_id, _DIRECTION_DOWNLINK), empty).bitrate,
                    ul_bitrate=self._flow_dict.get((drb_id, _DIRECTION_UPLINK), empty).bitrate,
                )
                for drb_id in drb_id_array
            ]
        )
