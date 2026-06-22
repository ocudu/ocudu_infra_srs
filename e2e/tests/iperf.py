# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Test Iperf
"""

import logging
from time import sleep
from typing import Optional, Sequence, Tuple, Union

import pytest
from google.protobuf.empty_pb2 import Empty
from pytest import mark
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.utils import configure_artifacts, param
from retina.protocol.base_pb2 import Metrics, PLMN
from retina.protocol.channel_emulator_pb2_grpc import ChannelEmulatorStub
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import GNBStub
from retina.protocol.ric_pb2_grpc import NearRtRicStub
from retina.protocol.ue_pb2 import IPerfDir, IPerfProto
from retina.protocol.ue_pb2_grpc import UEStub

from .steps.configuration import (
    configure_test_parameters,
    get_minimum_sample_rate_for_bandwidth,
)
from .steps.iperf_helpers import (
    assess_iperf_bitrate,
    get_maximum_throughput,
    LOW_BITRATE,
    MEDIUM_BITRATE,
    SHORT_DURATION,
)
from .steps.stub import (
    INTER_UE_START_PERIOD,
    iperf_parallel,
    ric_validate_e2_interface,
    start_and_attach,
    start_kpm_mon_xapp,
    start_rc_xapp,
    stop,
    stop_kpm_mon_xapp,
    stop_rc_xapp,
    UE_STARTUP_TIMEOUT,
)


@mark.parametrize(
    "direction",
    (
        param(IPerfDir.DOWNLINK, id="downlink", marks=mark.downlink),
        param(IPerfDir.UPLINK, id="uplink", marks=mark.uplink),
        param(IPerfDir.BIDIRECTIONAL, id="bidirectional", marks=mark.bidirectional),
    ),
)
@mark.parametrize(
    "protocol",
    (
        param(IPerfProto.UDP, id="udp", marks=mark.udp),
        param(IPerfProto.TCP, id="tcp", marks=mark.tcp),
    ),
)
@mark.parametrize(
    "band, common_scs, bandwidth",
    (param(3, 15, 10, id="band:%s-scs:%s-bandwidth:%s"),),
)
@mark.zmq_srsue
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_srsue(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue: UEStub,  # pylint: disable=invalid-name
    fivegc: FiveGCStub,
    gnb: GNBStub,
    band: int,
    common_scs: int,
    bandwidth: int,
    protocol: IPerfProto,
    direction: IPerfDir,
):
    """
    ZMQ IPerfs
    """

    _iperf(
        retina_manager=retina_manager,
        retina_data=retina_data,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        band=band,
        common_scs=common_scs,
        bandwidth=bandwidth,
        sample_rate=11520000,
        iperf_duration=SHORT_DURATION,
        protocol=protocol,
        bitrate=MEDIUM_BITRATE,
        direction=direction,
        global_timing_advance=-1,
        time_alignment_calibration=0,
        always_download_artifacts=True,
        common_search_space_enable=True,
        prach_config_index=1,
        pdsch_mcs_table="qam64",
        pusch_mcs_table="qam64",
    )


@mark.parametrize(
    "direction",
    (param(IPerfDir.BIDIRECTIONAL, id="bidirectional", marks=mark.bidirectional),),
)
@mark.parametrize(
    "protocol",
    (param(IPerfProto.UDP, id="udp", marks=mark.udp),),
)
@mark.parametrize(
    "band, common_scs, bandwidth",
    (param(3, 15, 10, id="band:%s-scs:%s-bandwidth:%s"),),
)
@mark.zmq_ric
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_ric(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue: UEStub,  # pylint: disable=invalid-name
    fivegc: FiveGCStub,
    gnb: GNBStub,
    ric: NearRtRicStub,
    band: int,
    common_scs: int,
    bandwidth: int,
    protocol: IPerfProto,
    direction: IPerfDir,
):
    """
    ZMQ IPerfs
    """

    _iperf(
        retina_manager=retina_manager,
        retina_data=retina_data,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        band=band,
        common_scs=common_scs,
        bandwidth=bandwidth,
        sample_rate=11520000,
        iperf_duration=SHORT_DURATION,
        protocol=protocol,
        bitrate=LOW_BITRATE,
        direction=direction,
        global_timing_advance=-1,
        time_alignment_calibration=0,
        always_download_artifacts=True,
        common_search_space_enable=True,
        prach_config_index=1,
        pdsch_mcs_table="qam64",
        pusch_mcs_table="qam64",
        ric=ric,
    )


@mark.parametrize(
    "direction",
    (
        param(IPerfDir.DOWNLINK, id="downlink", marks=mark.downlink),
        param(IPerfDir.UPLINK, id="uplink", marks=mark.uplink),
        param(IPerfDir.BIDIRECTIONAL, id="bidirectional", marks=mark.bidirectional),
    ),
)
@mark.parametrize(
    "protocol",
    (
        param(IPerfProto.UDP, id="udp", marks=mark.udp),
        param(IPerfProto.TCP, id="tcp", marks=mark.tcp),
    ),
)
@mark.parametrize(
    "band, common_scs, bandwidth",
    (
        param(3, 15, 10, id="band:%s-scs:%s-bandwidth:%s"),
        param(78, 30, 20, id="band:%s-scs:%s-bandwidth:%s"),
    ),
)
@mark.android
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_android(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue: UEStub,  # pylint: disable=invalid-name
    fivegc: FiveGCStub,
    gnb: GNBStub,
    band: int,
    common_scs: int,
    bandwidth: int,
    protocol: IPerfProto,
    direction: IPerfDir,
):
    """
    Android IPerfs
    """

    _iperf(
        retina_manager=retina_manager,
        retina_data=retina_data,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        band=band,
        common_scs=common_scs,
        bandwidth=bandwidth,
        sample_rate=get_minimum_sample_rate_for_bandwidth(bandwidth),
        iperf_duration=SHORT_DURATION,
        protocol=protocol,
        bitrate=get_maximum_throughput(bandwidth=bandwidth, band=band, direction=direction, protocol=protocol),
        direction=direction,
        global_timing_advance=-1,
        time_alignment_calibration="auto",
        always_download_artifacts=True,
        warning_as_errors=False,
    )


@mark.parametrize(
    "direction",
    (param(IPerfDir.BIDIRECTIONAL, id="bidirectional", marks=mark.bidirectional),),
)
@mark.parametrize(
    "protocol",
    (param(IPerfProto.UDP, id="udp", marks=mark.udp),),
)
@mark.parametrize(
    "band, common_scs, bandwidth",
    (param(78, 30, 20, id="band:%s-scs:%s-bandwidth:%s"),),
)
@mark.android
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_android_interleaving(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue: UEStub,  # pylint: disable=invalid-name
    fivegc: FiveGCStub,
    gnb: GNBStub,
    band: int,
    common_scs: int,
    bandwidth: int,
    protocol: IPerfProto,
    direction: IPerfDir,
):
    """
    Android IPerfs Interleaving
    """

    _iperf(
        retina_manager=retina_manager,
        retina_data=retina_data,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        band=band,
        common_scs=common_scs,
        bandwidth=bandwidth,
        sample_rate=get_minimum_sample_rate_for_bandwidth(bandwidth),
        iperf_duration=SHORT_DURATION,
        protocol=protocol,
        bitrate=get_maximum_throughput(bandwidth=bandwidth, band=band, direction=direction, protocol=protocol),
        direction=direction,
        global_timing_advance=-1,
        time_alignment_calibration="auto",
        always_download_artifacts=True,
        warning_as_errors=False,
        pdsch_interleaving_bundle_size=2,
    )


@mark.parametrize(
    "direction",
    (
        param(IPerfDir.DOWNLINK, id="downlink", marks=mark.downlink),
        param(IPerfDir.UPLINK, id="uplink", marks=mark.uplink),
        param(IPerfDir.BIDIRECTIONAL, id="bidirectional", marks=mark.bidirectional),
    ),
)
@mark.parametrize(
    "protocol",
    (
        param(IPerfProto.UDP, id="udp", marks=mark.udp),
        param(IPerfProto.TCP, id="tcp", marks=mark.tcp),
    ),
)
@mark.parametrize(
    "band, common_scs, bandwidth",
    (
        param(7, 15, 20, id="band:%s-scs:%s-bandwidth:%s"),
        param(78, 30, 50, id="band:%s-scs:%s-bandwidth:%s"),
    ),
)
@mark.android_hp
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_android_hp(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue: UEStub,  # pylint: disable=invalid-name
    fivegc: FiveGCStub,
    gnb: GNBStub,
    band: int,
    common_scs: int,
    bandwidth: int,
    protocol: IPerfProto,
    direction: IPerfDir,
):
    """
    Android high performance IPerfs
    """

    _iperf(
        retina_manager=retina_manager,
        retina_data=retina_data,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        band=band,
        common_scs=common_scs,
        bandwidth=bandwidth,
        sample_rate=None,
        iperf_duration=SHORT_DURATION,
        protocol=protocol,
        bitrate=get_maximum_throughput(bandwidth=bandwidth, band=band, direction=direction, protocol=protocol),
        direction=direction,
        global_timing_advance=-1,
        time_alignment_calibration="auto",
        always_download_artifacts=True,
        warning_as_errors=False,
        gnb_post_cmd=("ru_sdr expert_cfg --low_phy_dl_throttling=0.5",),
    )


# pylint: disable=too-many-arguments,too-many-positional-arguments, too-many-locals
def _iperf(
    *,  # This enforces keyword-only arguments
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue_array: Sequence[UEStub],
    fivegc: FiveGCStub,
    gnb: GNBStub,
    band: int,
    common_scs: int,
    bandwidth: int,
    sample_rate: Optional[int],
    iperf_duration: int,
    bitrate: int,
    protocol: IPerfProto,
    direction: IPerfDir,
    global_timing_advance: int,
    time_alignment_calibration: Union[int, str],
    always_download_artifacts: bool,
    warning_as_errors: bool = True,
    bitrate_threshold: float = 0,  # bitrate != 0
    ue_startup_timeout: int = UE_STARTUP_TIMEOUT,
    gnb_post_cmd: Tuple[str, ...] = tuple(),
    plmn: Optional[PLMN] = None,
    common_search_space_enable: bool = False,
    prach_config_index=-1,
    ue_stop_timeout: int = 0,
    rx_to_tx_latency: int = -1,
    enable_dddsu: bool = False,
    nof_antennas_dl: int = 1,
    nof_antennas_ul: int = 1,
    pdsch_mcs_table: str = "qam256",
    pusch_mcs_table: str = "qam256",
    inter_ue_start_period=INTER_UE_START_PERIOD,
    ric: Optional[NearRtRicStub] = None,
    assess_bitrate: bool = False,
    stop_gnb_first: bool = False,
    packet_length: int = 0,
    channel_emulator: Optional[ChannelEmulatorStub] = None,
    min_dl_bitrate: float = 0,
    min_ul_bitrate: float = 0,
    pdsch_interleaving_bundle_size: int = 0,
    parallel_iperfs: int = 8,
):
    wait_before_power_off = 5

    logging.info("Iperf Test")

    configure_test_parameters(
        retina_manager=retina_manager,
        retina_data=retina_data,
        band=band,
        common_scs=common_scs,
        bandwidth=bandwidth,
        sample_rate=sample_rate,
        global_timing_advance=global_timing_advance,
        time_alignment_calibration=time_alignment_calibration,
        common_search_space_enable=common_search_space_enable,
        prach_config_index=prach_config_index,
        rx_to_tx_latency=rx_to_tx_latency,
        enable_dddsu=enable_dddsu,
        nof_antennas_dl=nof_antennas_dl,
        nof_antennas_ul=nof_antennas_ul,
        pdsch_mcs_table=pdsch_mcs_table,
        pusch_mcs_table=pusch_mcs_table,
        pdsch_interleaving_bundle_size=pdsch_interleaving_bundle_size,
    )

    configure_artifacts(
        retina_data=retina_data,
        always_download_artifacts=always_download_artifacts,
    )

    ue_attach_info_dict = start_and_attach(
        ue_array=ue_array,
        gnb=gnb,
        fivegc=fivegc,
        gnb_post_cmd=gnb_post_cmd,
        plmn=plmn,
        inter_ue_start_period=inter_ue_start_period,
        ric=ric,
        channel_emulator=channel_emulator,
        ue_startup_timeout=ue_startup_timeout,
    )

    if ric:
        start_rc_xapp(ric=ric)
        start_kpm_mon_xapp(ric=ric, metrics="DRB.UEThpDl,DRB.UEThpUl")

    iperf_parallel(
        ue_attach_info_dict=ue_attach_info_dict,
        fivegc=fivegc,
        protocol=protocol,
        direction=direction,
        iperf_duration=iperf_duration,
        bitrate=bitrate,
        packet_length=packet_length,
        bitrate_threshold_ratio=bitrate_threshold,
        parallel_iperfs=parallel_iperfs,
    )

    if ric:
        stop_rc_xapp(ric)
        stop_kpm_mon_xapp(ric)

    sleep(wait_before_power_off)
    if ric:
        ric_validate_e2_interface(ric=ric, kpm_expected=True, rc_expected=True)

    stop(
        ue_array=ue_array,
        gnb_array=[gnb],
        fivegc_array=[fivegc],
        retina_data=retina_data,
        ue_stop_timeout=ue_stop_timeout,
        warning_as_errors=warning_as_errors,
        ric=ric,
        stop_gnb_first=stop_gnb_first,
    )

    metrics: Metrics = gnb.GetMetrics(Empty())

    if metrics.aggregate.dl_bitrate + metrics.aggregate.ul_bitrate <= 0:
        pytest.fail("No traffic detected in GNB metrics")

    if assess_bitrate and protocol == IPerfProto.UDP:

        assess_iperf_bitrate(
            bw=bandwidth,
            band=band,
            nof_antennas_dl=nof_antennas_dl,
            pdsch_mcs_table=pdsch_mcs_table,
            pusch_mcs_table=pusch_mcs_table,
            iperf_duration=iperf_duration,
            metrics=metrics,
            dl_brate_threshold=min_dl_bitrate,
            ul_brate_threshold=min_ul_bitrate,
        )
