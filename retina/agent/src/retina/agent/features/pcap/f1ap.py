# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
F1AP-layer pcap analyzers.
"""

from typing import Optional

from retina.agent.features.pcap.rrc import ReestablishmentAnalyzer as RlcReestablishmentAnalyzer


class ReestablishmentAnalyzer(RlcReestablishmentAnalyzer):
    """
    Counts RRC Reestablishment requests and completions.

    - UL RRCReestablishmentRequest (nr-rrc.rrcReestablishmentRequest_element), carried in
      F1AP InitialULRRCMessageTransfer.
    - UL RRCReestablishmentComplete (nr-rrc.rrcReestablishmentComplete_element), carried in
      F1AP ULRRCMessageTransfer.

    Unlike the MAC-NR/RLC-NR captures, the DU's RLC layer has already resolved any ARQ
    retransmission before forwarding the reassembled SDU over F1AP, so each logical message
    appears exactly once here. Disable the base class's retransmission dedup (it's a no-op
    once _ueid always returns None) since it's both unneeded and unavailable: F1AP-layer
    packets don't carry the rlc-nr.ueid field the dedup keys off of.
    """

    @staticmethod
    def _ueid(packet) -> Optional[int]:
        return None
