# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Test Iperf
"""

from time import sleep
from typing import Dict, Optional, Sequence, Tuple

import pytest
from google.protobuf.empty_pb2 import Empty
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import CriteriaTable
from retina.launcher.utils import configure_artifacts
from retina.protocol import (
    FiveGCClient,
    GNBClient,
    NearRtRicClient,
    UEClient,
)
from retina.protocol.base_pb2 import Metrics, PLMN
from retina.protocol.ue_pb2 import IPerfDir, IPerfProto

from .steps.configuration import set_config_files
from .steps.stub import (
    INTER_UE_START_PERIOD,
    start_and_attach,
    start_kpm_mon_xapp,
    start_rc_xapp,
    stop,
    stop_kpm_mon_xapp,
    stop_rc_xapp,
    UE_STARTUP_TIMEOUT,
)
from .steps.test_loader import load_tests, RetinaTestDefinition
from .steps.traffic import iperf_parallel

# Default iperf duration when a test suite does not give one
SHORT_DURATION = 20

# Iperf protocols and directions as named in the test suites
_IPERF_PROTOCOLS: Dict[str, "IPerfProto.ValueType"] = {
    "udp": IPerfProto.UDP,
    "tcp": IPerfProto.TCP,
}
_IPERF_DIRECTIONS: Dict[str, "IPerfDir.ValueType"] = {
    "downlink": IPerfDir.DOWNLINK,
    "uplink": IPerfDir.UPLINK,
    "bidirectional": IPerfDir.BIDIRECTIONAL,
}


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEClient,  # pylint: disable=invalid-name
    gnb: GNBClient,
    fivegc: FiveGCClient,
):
    """
    Template test function for iperfs between the UE and the core. The protocol, the direction, the
    bitrate to request and the duration come from the parameters of the test. A bidirectional iperf
    requests a single bitrate in both directions, so it takes the uplink one
    """

    parameters = test_definition.parameters
    direction = _IPERF_DIRECTIONS[parameters["direction"]]

    _gnb_iperf(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        protocol=_IPERF_PROTOCOLS[parameters["protocol"]],
        direction=direction,
        bitrate=int(parameters["dl_bitrate"] if direction == IPerfDir.DOWNLINK else parameters["ul_bitrate"]),
        duration=parameters.get("duration", SHORT_DURATION),
    )


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb_ric(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEClient,  # pylint: disable=invalid-name
    gnb: GNBClient,
    fivegc: FiveGCClient,
    ric: NearRtRicClient,
):
    """
    Same as test_gnb, with a Near-RT RIC attached over E2. The RC and KPM xApps run for the whole
    iperf, and the ric criteria of the test assert the E2 interface worked
    """

    parameters = test_definition.parameters
    direction = _IPERF_DIRECTIONS[parameters["direction"]]

    _gnb_iperf(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        protocol=_IPERF_PROTOCOLS[parameters["protocol"]],
        direction=direction,
        bitrate=int(parameters["dl_bitrate"] if direction == IPerfDir.DOWNLINK else parameters["ul_bitrate"]),
        duration=parameters.get("duration", SHORT_DURATION),
        ric=ric,
    )


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _gnb_iperf(
    *,  # This enforces keyword-only arguments
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue_array: Sequence[UEClient],
    gnb: GNBClient,
    fivegc: FiveGCClient,
    protocol: "IPerfProto.ValueType",
    direction: "IPerfDir.ValueType",
    bitrate: int,
    duration: int,
    ric: Optional[NearRtRicClient] = None,
):
    set_config_files(retina_manager=retina_manager, retina_data=retina_data, test_definition=test_definition)
    configure_artifacts(retina_data=retina_data, always_download_artifacts=True)

    for criteria_id, criteria_expected_value in test_definition.criteria.items():
        criteria.add_criteria(criteria_id, criteria_expected_value)

    try:
        _run_iperf(
            retina_data=retina_data,
            ue_array=ue_array,
            fivegc=fivegc,
            gnb=gnb,
            iperf_duration=duration,
            bitrate=bitrate,
            protocol=protocol,
            direction=direction,
            warning_as_errors=False,
            ric=ric,
        )
    finally:
        criteria.validate()


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def _run_iperf(
    *,  # This enforces keyword-only arguments
    retina_data: RetinaTestData,
    ue_array: Sequence[UEClient],
    fivegc: FiveGCClient,
    gnb: GNBClient,
    iperf_duration: int,
    bitrate: int,
    protocol: "IPerfProto.ValueType",
    direction: "IPerfDir.ValueType",
    warning_as_errors: bool = True,
    bitrate_threshold: float = 0,  # bitrate != 0
    ue_startup_timeout: int = UE_STARTUP_TIMEOUT,
    gnb_post_cmd: Tuple[str, ...] = tuple(),
    plmn: Optional[PLMN] = None,
    ue_stop_timeout: int = 0,
    inter_ue_start_period=INTER_UE_START_PERIOD,
    ric: Optional[NearRtRicClient] = None,
    stop_gnb_first: bool = False,
    packet_length: int = 0,
    parallel_iperfs: int = 8,
) -> Metrics:
    wait_before_power_off = 5

    ue_attach_info_dict = start_and_attach(
        ue_array=ue_array,
        gnb=gnb,
        fivegc=fivegc,
        gnb_post_cmd=gnb_post_cmd,
        plmn=plmn,
        inter_ue_start_period=inter_ue_start_period,
        ric=ric,
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

    return metrics
