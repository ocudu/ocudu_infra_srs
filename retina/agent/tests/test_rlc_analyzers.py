# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for the RLC pcap analyzers: DrbTrafficAnalyzer.
"""

import unittest

from retina.agent.features.pcap.rlc import DrbTrafficAnalyzer

_DIRECTION_UPLINK = 0
_DIRECTION_DOWNLINK = 1


# ── Packet factory helpers ────────────────────────────────────────────────────


class _FakeLayer:  # pylint: disable=too-few-public-methods
    """The rlc-nr layer of a packet, as pyshark exposes it."""

    def __init__(self, bearer_id, direction, pdu_length):
        self.field_names = ["bearer_id", "direction", "pdu_length"]
        self.bearer_id = str(bearer_id)
        self.direction = str(direction)
        self.pdu_length = str(pdu_length)


class _FakeOtherLayer:  # pylint: disable=too-few-public-methods
    """A layer of some other protocol, which the analyzer has to look past."""

    def __init__(self):
        self.field_names = ["src", "dst"]


class _FakePacket:  # pylint: disable=too-few-public-methods
    """A captured packet, carrying a single layer."""

    def __init__(self, layer, timestamp):
        self.layers = [layer]
        self.sniff_timestamp = str(timestamp)


def make_packet(bearer_id, direction, pdu_length, timestamp):
    return _FakePacket(_FakeLayer(bearer_id, direction, pdu_length), timestamp)


def drb_of(metrics, drb_id):
    return next(drb for drb in metrics.drb_array if drb.drb_id == drb_id)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDrbTrafficAnalyzer(unittest.TestCase):
    """Bytes and rates the analyzer attributes to each bearer."""

    def test_no_packets_reports_no_bearer(self):
        self.assertEqual(len(DrbTrafficAnalyzer().report().drb_array), 0)

    def test_bytes_add_up_per_bearer_and_direction(self):
        analyzer = DrbTrafficAnalyzer()
        analyzer.process(make_packet(1, _DIRECTION_DOWNLINK, 1000, 10.0))
        analyzer.process(make_packet(1, _DIRECTION_DOWNLINK, 500, 11.0))
        analyzer.process(make_packet(1, _DIRECTION_UPLINK, 200, 11.0))
        analyzer.process(make_packet(2, _DIRECTION_DOWNLINK, 300, 11.0))

        metrics = analyzer.report()
        self.assertEqual([drb.drb_id for drb in metrics.drb_array], [1, 2])
        self.assertEqual(drb_of(metrics, 1).dl_bytes, 1500)
        self.assertEqual(drb_of(metrics, 1).ul_bytes, 200)
        self.assertEqual(drb_of(metrics, 2).dl_bytes, 300)
        self.assertEqual(drb_of(metrics, 2).ul_bytes, 0)

    def test_bitrate_is_the_bytes_over_the_span_they_came_in(self):
        analyzer = DrbTrafficAnalyzer()
        for i in range(10):
            analyzer.process(make_packet(1, _DIRECTION_DOWNLINK, 1000, 100.0 + i))

        # 10 kB over the 9 s between the first and the last PDU
        self.assertAlmostEqual(drb_of(analyzer.report(), 1).dl_bitrate, 10000 * 8 / 9)

    def test_a_single_pdu_spans_no_time_and_reports_no_rate(self):
        analyzer = DrbTrafficAnalyzer()
        analyzer.process(make_packet(1, _DIRECTION_DOWNLINK, 1000, 100.0))

        metrics = analyzer.report()
        self.assertEqual(drb_of(metrics, 1).dl_bytes, 1000)
        self.assertEqual(drb_of(metrics, 1).dl_bitrate, 0.0)

    def test_the_directions_of_a_bearer_are_timed_apart(self):
        analyzer = DrbTrafficAnalyzer()
        analyzer.process(make_packet(1, _DIRECTION_DOWNLINK, 1000, 100.0))
        analyzer.process(make_packet(1, _DIRECTION_DOWNLINK, 1000, 102.0))
        # The uplink of the same bearer starts later and lasts half as long
        analyzer.process(make_packet(1, _DIRECTION_UPLINK, 1000, 101.0))
        analyzer.process(make_packet(1, _DIRECTION_UPLINK, 1000, 102.0))

        metrics = analyzer.report()
        self.assertAlmostEqual(drb_of(metrics, 1).dl_bitrate, 2000 * 8 / 2)
        self.assertAlmostEqual(drb_of(metrics, 1).ul_bitrate, 2000 * 8 / 1)

    def test_a_packet_the_fields_cannot_be_read_from_is_skipped(self):
        analyzer = DrbTrafficAnalyzer()
        analyzer.process(make_packet(1, _DIRECTION_DOWNLINK, "not a length", 100.0))
        analyzer.process(_FakePacket(_FakeOtherLayer(), 100.0))
        analyzer.process(make_packet(1, _DIRECTION_DOWNLINK, 1000, 100.0))

        self.assertEqual(drb_of(analyzer.report(), 1).dl_bytes, 1000)

    def test_the_display_filter_selects_drbs(self):
        self.assertEqual(DrbTrafficAnalyzer().display_filter, "rlc-nr.bearer-type == 5")


if __name__ == "__main__":
    unittest.main()
