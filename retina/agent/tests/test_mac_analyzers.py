# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for the MAC pcap analyzers: DifferentialKoffsetAnalyzer.
"""

import unittest

from retina.agent.features.pcap.mac import DifferentialKoffsetAnalyzer

# ── Packet factory helpers ────────────────────────────────────────────────────


class _FakeLayer:  # pylint: disable=too-few-public-methods
    """The mac-nr layer of a packet, as pyshark exposes it."""

    def __init__(self, koffset):
        self.differential_koffset = str(koffset)


class _FakePacket:  # pylint: disable=too-few-public-methods
    """A captured packet, carrying a mac-nr layer."""

    def __init__(self, layer):
        self._layer = layer

    def __getitem__(self, name):
        if name != "mac-nr":
            raise KeyError(name)
        return self._layer


class _FakeOtherPacket:  # pylint: disable=too-few-public-methods
    """A captured packet of some other protocol, which the analyzer has to look past."""

    def __getitem__(self, name):
        raise KeyError(name)


def make_packet(koffset):
    return _FakePacket(_FakeLayer(koffset))


def koffsets_of(koffset_array):
    analyzer = DifferentialKoffsetAnalyzer()
    for koffset in koffset_array:
        analyzer.process(make_packet(koffset))
    return list(analyzer.report().du.differential_koffset_array)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDifferentialKoffsetAnalyzer(unittest.TestCase):
    """Values the analyzer takes from the Differential Koffset MAC CEs of a capture."""

    def test_no_packets_reports_no_koffset(self):
        self.assertEqual(koffsets_of([]), [])

    def test_single_value_is_reported(self):
        self.assertEqual(koffsets_of([11]), [11])

    def test_values_are_kept_in_the_order_they_were_sent(self):
        self.assertEqual(koffsets_of([10, 11, 12, 13, 14]), [10, 11, 12, 13, 14])

    def test_repeated_value_is_recorded_once(self):
        # A retransmitted MAC CE, and the value in force signalled again after one was lost.
        self.assertEqual(koffsets_of([12, 12, 12]), [12])

    def test_value_returning_is_recorded_again(self):
        # The round trip of a pass falls and grows again, so an earlier value comes back.
        self.assertEqual(koffsets_of([12, 11, 12]), [12, 11, 12])

    def test_zero_is_a_value_like_any_other(self):
        # The derivation clamps at zero once the round trip leaves no room under the cell-specific Koffset.
        self.assertEqual(koffsets_of([11, 0]), [11, 0])

    def test_packet_without_the_field_is_ignored(self):
        analyzer = DifferentialKoffsetAnalyzer()
        analyzer.process(make_packet(12))
        analyzer.process(_FakePacket(object()))
        analyzer.process(make_packet(12))
        self.assertEqual(list(analyzer.report().du.differential_koffset_array), [12])

    def test_packet_of_another_protocol_is_ignored(self):
        analyzer = DifferentialKoffsetAnalyzer()
        analyzer.process(make_packet(12))
        analyzer.process(_FakeOtherPacket())
        analyzer.process(make_packet(13))
        self.assertEqual(list(analyzer.report().du.differential_koffset_array), [12, 13])
