# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
PUCCH Tests
"""

import logging
from typing import Callable, Tuple

from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from pytest import fail, mark, param
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.protocol.base_pb2 import Metrics
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import GNBStub
from retina.protocol.ue_pb2 import IPerfDir, IPerfProto
from retina.protocol.ue_pb2_grpc import UEStub

from tests.steps.stub import iperf_parallel, start_network, stop, ue_start_and_attach

from .steps.configuration import configure_test_parameters, get_minimum_sample_rate_for_bandwidth


@mark.zmq
@mark.parametrize(
    "pucch_formats, ul_noise_spd",
    (
        # PUCCH Format 0 decoder doesn't work with no noise.
        param("f0_and_f2", -134, id="f0_f2"),
        param("f1_and_f2", 0, id="f1_f2"),
        param("f1_and_f3", 0, id="f1_f3"),
        param("f1_and_f4", 0, id="f1_f4"),
    ),
)
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def test_pucch(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue_multiple: Callable[[int], Tuple[UEStub, ...]],
    fivegc: FiveGCStub,
    gnb: GNBStub,
    pucch_formats: str,
    ul_noise_spd: int,
):
    """
    Test PUCCH (Amarisoft, ZMQ)
    """

    ue_array = ue_multiple(32)

    band = 41
    common_scs = 30
    bandwidth = 50
    iperf_duration = 10
    iperf_bitrate = int(1e6)
    f0_or_f1 = pucch_formats[:2]
    f2_or_f3_or_f4 = pucch_formats[-2:]

    configure_test_parameters(
        retina_manager=retina_manager,
        retina_data=retina_data,
        band=band,
        common_scs=common_scs,
        bandwidth=bandwidth,
        sample_rate=get_minimum_sample_rate_for_bandwidth(bandwidth),
        global_timing_advance=0,
        time_alignment_calibration=0,
        pucch_formats=pucch_formats,
        ul_noise_spd=ul_noise_spd,
    )

    logging.info("PUCCH %s Test", pucch_formats)

    start_network(ue_array=ue_array, gnb_array=[gnb], fivegc_array=[fivegc])
    ue_attach_info_dict = ue_start_and_attach(
        ue_array=ue_array, du_definition=[gnb.GetDefinition(UInt32Value(value=0))], fivegc_array=[fivegc]
    )

    # DL iperf test
    iperf_parallel(
        ue_attach_info_dict=ue_attach_info_dict,
        fivegc=fivegc,
        protocol=IPerfProto.UDP,
        direction=IPerfDir.DOWNLINK,
        iperf_duration=iperf_duration,
        bitrate=iperf_bitrate,
    )

    # Bidirectional iperf test
    iperf_parallel(
        ue_attach_info_dict=ue_attach_info_dict,
        fivegc=fivegc,
        protocol=IPerfProto.UDP,
        direction=IPerfDir.BIDIRECTIONAL,
        iperf_duration=iperf_duration,
        bitrate=iperf_bitrate,
    )

    stop(
        ue_array=ue_array,
        gnb_array=[gnb],
        fivegc_array=[fivegc],
        retina_data=retina_data,
        fail_if_kos=True,
    )

    metrics: Metrics = gnb.GetMetrics(Empty())
    invalid_pucchs = (
        metrics.nof_pucch_f0f1_invalid_harqs > 0
        or metrics.nof_pucch_f2f3f4_invalid_harqs > 0
        or metrics.nof_pucch_f2f3f4_invalid_csis > 0
    )

    if invalid_pucchs:
        fail(
            f"Invalid PUCCH transmissions during the test: "
            f"harq_{f0_or_f1}={metrics.nof_pucch_f0f1_invalid_harqs} "
            f"harq_{f2_or_f3_or_f4}={metrics.nof_pucch_f2f3f4_invalid_harqs} "
            f"csi_{f2_or_f3_or_f4}={metrics.nof_pucch_f2f3f4_invalid_csis}"
        )
