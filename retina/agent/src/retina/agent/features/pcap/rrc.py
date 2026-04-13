# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
5G NR RRC-layer pcap analyzers.
"""

from retina.protocol.base_pb2 import Metrics

from retina.agent.features.pcap.analyzer import PcapAnalyzer


def _rrc_layer(packet):
    """Return the layer that contains nr_rrc_* fields (e.g. mac-nr or rlc-nr)."""
    for layer in packet.layers:
        if any(f.startswith("nr_rrc_") for f in layer.field_names):
            return layer
    raise KeyError("No NR-RRC layer found in packet")


class HandoverAnalyzer(PcapAnalyzer):
    """
    Counts DL RRCReconfiguration messages carrying reconfigurationWithSync.

    Each such message corresponds to a handover command sent to a UE.
    tshark display filter: nr-rrc.reconfigurationWithSync_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "nr-rrc.reconfigurationWithSync_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(nof_handovers=self._count)


class PrachConfigIndexAnalyzer(PcapAnalyzer):
    """
    Extracts the PRACH configuration index from a MAC-NR capture.

    Reads the nr-rrc.prach_ConfigurationIndex field from the first matching
    RRC System Information packet. The result is available via the
    prach_config_index property after analysis.
    """

    def __init__(self) -> None:
        self._prach_config_index: int = -1

    @property
    def display_filter(self) -> str:
        return "nr-rrc.prach_ConfigurationIndex"

    @property
    def prach_config_index(self) -> int:
        """Return the PRACH configuration index found in the capture, or -1 if not found."""
        return self._prach_config_index

    def process(self, packet) -> None:
        if self._prach_config_index < 0:
            try:
                self._prach_config_index = int(_rrc_layer(packet).nr_rrc_prach_configurationindex)
            except (AttributeError, KeyError, ValueError):
                pass

    def report(self) -> Metrics:
        return Metrics(prach_configuration_index=self._prach_config_index)


class SibAnalyzer(PcapAnalyzer):
    """
    Counts transmissions of SIB2, SIB3, SIB4 and SIB5 in a MAC-NR capture.

    Each SIB is carried inside a SystemInformation message. The per-SIB count
    is available via sib_count(n) after analysis.
    tshark display filters: nr-rrc.sib2_element, nr-rrc.sib3_element, ...
    """

    _SIBS = (1, 2, 3, 4, 5, 8)

    def __init__(self) -> None:
        self._counts = {n: 0 for n in self._SIBS}

    @property
    def display_filter(self) -> str:
        parts = []
        for n in self._SIBS:
            parts.append("nr-rrc.systemInformationBlockType1_element" if n == 1 else f"nr-rrc.sib{n}_element")
        return " || ".join(parts)

    def sib_count(self, n: int) -> int:
        """Return the number of packets containing SIBn."""
        return self._counts.get(n, 0)

    def process(self, packet) -> None:
        try:
            layer = _rrc_layer(packet)
        except KeyError:
            return
        for n in self._SIBS:
            field = "nr_rrc_systeminformationblocktype1_element" if n == 1 else f"nr_rrc_sib{n}_element"
            try:
                getattr(layer, field)
                self._counts[n] += 1
            except AttributeError:
                pass

    def report(self) -> Metrics:
        return Metrics(
            nof_sib1_transmissions=self._counts[1],
            nof_sib2_transmissions=self._counts[2],
            nof_sib3_transmissions=self._counts[3],
            nof_sib4_transmissions=self._counts[4],
            nof_sib5_transmissions=self._counts[5],
            nof_sib8_transmissions=self._counts[8],
        )


class TransformPrecoderAnalyzer(PcapAnalyzer):
    """
    Extracts the transformPrecoder value from PUSCH-Config in a MAC-NR capture.

    Reads the nr-rrc.transformPrecoder field from the first matching RRC message.
    The value follows the NR-RRC enumeration: enabled(0), disabled(1).
    tshark display filter: nr-rrc.transformPrecoder
    """

    def __init__(self) -> None:
        self._enabled = False

    @property
    def display_filter(self) -> str:
        return "nr-rrc.transformPrecoder==0"

    def process(self, packet) -> None:
        self._enabled = True

    def report(self) -> Metrics:
        return Metrics(transform_precoder=self._enabled)


class SrsFreqDomainAnalyzer(PcapAnalyzer):
    """
    Extracts c-SRS and b-SRS from freqDomainResources in SRS-Config (MAC-NR capture).

    Reads nr-rrc.c_SRS and nr-rrc.b_SRS from the first matching RRC message.
    tshark display filters: nr-rrc.c_SRS, nr-rrc.b_SRS
    """

    def __init__(self) -> None:
        self._c_srs: int = -1
        self._b_srs: int = -1

    @property
    def display_filter(self) -> str:
        return "nr-rrc.c_SRS || nr-rrc.b_SRS"

    def process(self, packet) -> None:
        if self._c_srs >= 0 and self._b_srs >= 0:
            return
        try:
            layer = _rrc_layer(packet)
            if self._c_srs < 0:
                try:
                    self._c_srs = int(layer.nr_rrc_c_srs)
                except AttributeError:
                    pass
            if self._b_srs < 0:
                try:
                    self._b_srs = int(layer.nr_rrc_b_srs)
                except AttributeError:
                    pass
        except KeyError:
            pass

    def report(self) -> Metrics:
        return Metrics(c_srs=self._c_srs, b_srs=self._b_srs)


class T312Analyzer(PcapAnalyzer):
    """
    Extracts the t312 value from rlf-TimersAndConstants in a MAC-NR capture.

    Reads the nr-rrc.t312 field from the first matching RRC message.
    tshark display filter: nr-rrc.t312
    """

    def __init__(self) -> None:
        self._value: int = -1

    @property
    def display_filter(self) -> str:
        return "nr-rrc.t312_r16"

    def process(self, packet) -> None:
        if self._value < 0:
            try:
                self._value = int(_rrc_layer(packet).nr_rrc_t312_r16)
            except (AttributeError, KeyError, ValueError):
                pass

    def report(self) -> Metrics:
        return Metrics(t312=self._value)


class DrxLongCycleAnalyzer(PcapAnalyzer):
    """
    Extracts the drx-LongCycleStartOffset value from a MAC-NR capture.

    Reads the nr-rrc.drx-LongCycleStartOffset field from the first matching
    RRC message containing a DRX configuration.
    tshark display filter: nr-rrc.drx_LongCycleStartOffset
    """

    def __init__(self) -> None:
        self._value: int = -1

    @property
    def display_filter(self) -> str:
        return "nr-rrc.drx_LongCycleStartOffset"

    def process(self, packet) -> None:
        if self._value < 0:
            try:
                self._value = int(_rrc_layer(packet).nr_rrc_drx_longcyclestartoffset)
            except (AttributeError, KeyError, ValueError):
                pass

    def report(self) -> Metrics:
        return Metrics(drx_long_cycle_start_offset=self._value)


class PagingAnalyzer(PcapAnalyzer):
    """
    Counts RRC Paging messages in a MAC-NR capture.

    tshark display filter: nr-rrc.paging_element
    """

    def __init__(self) -> None:
        self._count: int = 0

    @property
    def display_filter(self) -> str:
        return "nr-rrc.paging_element"

    def process(self, packet) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(nof_paging_messages=self._count)


class SuspendConfigAnalyzer(PcapAnalyzer):
    """
    Counts DL RRCRelease messages carrying suspendConfig.

    Each such message corresponds to a UE being suspended (RRC Inactive).
    tshark display filter: nr-rrc.suspendConfig_element
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "nr-rrc.suspendConfig_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(nof_rrc_suspend=self._count)


class ResumeRequestAnalyzer(PcapAnalyzer):
    """
    Counts UL RRCResumeRequest messages (covers both RRCResumeRequest and RRCResumeRequest1).

    tshark display filter: nr-rrc.rrcResumeRequest or nr-rrc.rrcResumeRequest1
    """

    def __init__(self) -> None:
        self._count = 0

    @property
    def display_filter(self) -> str:
        return "nr-rrc.rrcResumeRequest_element"

    def process(self, _) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(nof_rrc_resume_request=self._count)


class ReestablishmentAnalyzer(PcapAnalyzer):
    """
    Counts RRC Reestablishment complete.

    - UL DCCH RRCReestablishmentComplete (nr-rrc.rrcReestablishmentComplete_element)

    """

    def __init__(self) -> None:
        self._completion_count = 0

    @property
    def display_filter(self) -> str:
        return "nr-rrc.rrcReestablishmentComplete_element"

    def process(self, packet) -> None:
        self._completion_count += 1

    def report(self) -> Metrics:
        return Metrics(
            nof_reestablishments_complete=self._completion_count,
        )
