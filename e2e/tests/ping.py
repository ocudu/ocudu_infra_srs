# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Test ping
"""

import logging
from typing import Callable, List, Optional, Sequence, Tuple, Union

from _pytest.outcomes import Failed
from google.protobuf.wrappers_pb2 import UInt32Value
from pytest import mark
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import CriteriaTable
from retina.launcher.utils import configure_artifacts
from retina.protocol import FiveGCClient, GNBClient, UEClient
from retina.protocol.base_pb2 import PLMN

from .steps.configuration import configure_test_parameters, set_config_files
from .steps.stub import (
    GNB_STARTUP_TIMEOUT,
    start_network,
    stop,
    ue_start_and_attach,
    ue_stop,
    validate_ue_registered_via_ims,
)
from .steps.test_loader import load_tests, RetinaTestDefinition
from .steps.traffic import ping


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_rf_reattach(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEClient,  # pylint: disable=invalid-name
    gnb: GNBClient,
    fivegc: FiveGCClient,
):
    """Template test function for pings over the air, stopping and attaching the UE in between"""

    _rf_ping(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        reattach_count=2,
    )


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_rf_drx(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEClient,  # pylint: disable=invalid-name
    gnb: GNBClient,
    fivegc: FiveGCClient,
):
    """Template test function for pings over the air with a short interval, to exercise DRX"""

    _rf_ping(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        ping_interval=0.1,
    )


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_rf_ims(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEClient,  # pylint: disable=invalid-name
    gnb: GNBClient,
    fivegc: FiveGCClient,
):
    """Template test function for IMS pings over the air, using the IMS mode of the core config"""

    _rf_ping(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue_array=(ue,),
        gnb=gnb,
        fivegc=fivegc,
        ims_mode=test_definition.core.parameters["ims_mode"],
    )


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _rf_ping(
    *,  # This enforces keyword-only arguments
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue_array: Sequence[UEClient],
    gnb: GNBClient,
    fivegc: FiveGCClient,
    reattach_count: int = 0,
    ping_interval: float = 1.0,
    ims_mode: str = "",
):
    set_config_files(retina_manager=retina_manager, retina_data=retina_data, test_definition=test_definition)
    configure_artifacts(retina_data=retina_data, always_download_artifacts=True)

    for criteria_id, criteria_expected_value in test_definition.criteria.items():
        criteria.add_criteria(criteria_id, criteria_expected_value)

    try:
        _run_ping(
            retina_data=retina_data,
            ue_array=ue_array,
            gnb=gnb,
            fivegc=fivegc,
            warning_as_errors=False,
            reattach_count=reattach_count,
            ping_interval=ping_interval,
            ims_mode=ims_mode,
        )
    finally:
        criteria.validate()


@mark.example
def test_example(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue_multiple: Callable[[int], Tuple[UEClient, ...]],
    fivegc: FiveGCClient,
    gnb: GNBClient,
):
    """
    ZMQ Pings
    """
    _ping(
        retina_manager=retina_manager,
        retina_data=retina_data,
        ue_array=ue_multiple(4),
        gnb=gnb,
        fivegc=fivegc,
        band=3,
        common_scs=15,
        bandwidth=10,
        sample_rate=None,  # default from testbed
        global_timing_advance=0,
        time_alignment_calibration=0,
        ue_stop_timeout=3,
        enable_security_mode=False,
        post_command=("cu_cp --inactivity_timer=600", ""),
    )


@mark.example_srsue
def test_example_srsue(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue: Tuple[UEClient, ...],
    fivegc: FiveGCClient,
    gnb: GNBClient,
):
    """
    ZMQ Pings
    """

    _ping(
        retina_manager=retina_manager,
        retina_data=retina_data,
        ue_array=ue,
        gnb=gnb,
        fivegc=fivegc,
        band=3,
        common_scs=15,
        bandwidth=10,
        sample_rate=11520000,
        global_timing_advance=0,
        time_alignment_calibration=0,
        common_search_space_enable=True,
        prach_config_index=1,
        pdsch_mcs_table="qam64",
        pusch_mcs_table="qam64",
        ue_stop_timeout=3,
    )


# pylint: disable=too-many-arguments,too-many-positional-arguments, too-many-locals
def _ping(
    *,  # This enforces keyword-only arguments
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue_array: Sequence[UEClient],
    fivegc: FiveGCClient,
    gnb: GNBClient,
    band: int,
    common_scs: int,
    bandwidth: int,
    sample_rate: Optional[int],
    global_timing_advance: int,
    time_alignment_calibration: Union[int, str],
    log_search: bool = True,
    warning_as_errors: bool = True,
    always_download_artifacts: bool = False,
    ping_count: int = 10,
    reattach_count: int = 0,
    pre_command: Tuple[str, ...] = tuple(),
    post_command: Tuple[str, ...] = tuple(),
    gnb_stop_timeout: int = 0,
    ue_stop_timeout: int = 0,
    plmn: Optional[PLMN] = None,
    enable_security_mode: bool = False,
    ims_mode: str = "",
    enable_drx: bool = False,
    common_search_space_enable: bool = False,
    prach_config_index=-1,
    pdsch_mcs_table: str = "qam256",
    pusch_mcs_table: str = "qam256",
    ping_interval: float = 1.0,
    ul_noise_spd: int = 0,
    rx_to_tx_latency: int = -1,
    pdcch_log: bool = False,
    warning_allowlist: Optional[List[str]] = None,
    gnb_startup_timeout: int = GNB_STARTUP_TIMEOUT,
):
    logging.info("Ping Test")

    configure_test_parameters(
        retina_manager=retina_manager,
        retina_data=retina_data,
        band=band,
        common_scs=common_scs,
        bandwidth=bandwidth,
        sample_rate=sample_rate,
        global_timing_advance=global_timing_advance,
        time_alignment_calibration=time_alignment_calibration,
        n3_enable=True,
        log_ip_level="debug",
        enable_security_mode=enable_security_mode,
        ims_mode=ims_mode,
        enable_drx=enable_drx,
        common_search_space_enable=common_search_space_enable,
        prach_config_index=prach_config_index,
        pdsch_mcs_table=pdsch_mcs_table,
        pusch_mcs_table=pusch_mcs_table,
        ul_noise_spd=ul_noise_spd,
        rx_to_tx_latency=rx_to_tx_latency,
        pdcch_log=pdcch_log,
        warning_allowlist=warning_allowlist,
    )
    configure_artifacts(
        retina_data=retina_data,
        always_download_artifacts=always_download_artifacts,
    )

    _run_ping(
        retina_data=retina_data,
        ue_array=ue_array,
        fivegc=fivegc,
        gnb=gnb,
        log_search=log_search,
        warning_as_errors=warning_as_errors,
        ping_count=ping_count,
        reattach_count=reattach_count,
        pre_command=pre_command,
        post_command=post_command,
        gnb_stop_timeout=gnb_stop_timeout,
        ue_stop_timeout=ue_stop_timeout,
        plmn=plmn,
        ims_mode=ims_mode,
        ping_interval=ping_interval,
        gnb_startup_timeout=gnb_startup_timeout,
    )


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _run_ping(
    *,  # This enforces keyword-only arguments
    retina_data: RetinaTestData,
    ue_array: Sequence[UEClient],
    fivegc: FiveGCClient,
    gnb: GNBClient,
    log_search: bool = True,
    warning_as_errors: bool = True,
    ping_count: int = 10,
    reattach_count: int = 0,
    pre_command: Tuple[str, ...] = tuple(),
    post_command: Tuple[str, ...] = tuple(),
    gnb_stop_timeout: int = 0,
    ue_stop_timeout: int = 0,
    plmn: Optional[PLMN] = None,
    ims_mode: str = "",
    ping_interval: float = 1.0,
    gnb_startup_timeout: int = GNB_STARTUP_TIMEOUT,
):
    start_network(
        ue_array=ue_array,
        gnb_array=[gnb],
        fivegc_array=[fivegc],
        gnb_startup_timeout=gnb_startup_timeout,
        gnb_pre_cmd=pre_command,
        gnb_post_cmd=post_command,
        plmn=plmn,
    )
    ue_attach_info_dict = ue_start_and_attach(
        ue_array=ue_array,
        du_definition=[gnb.GetDefinition(UInt32Value(value=0)).du_definition],
        fivegc_array=[fivegc],
    )

    try:
        ping(ue_attach_info_dict=ue_attach_info_dict, fivegc=fivegc, ping_count=ping_count, ping_interval=ping_interval)

        # reattach and repeat if requested
        for _ in range(reattach_count):
            ue_stop(ue_array=ue_array, retina_data=retina_data)
            ue_attach_info_dict = ue_start_and_attach(
                ue_array=ue_array,
                du_definition=[gnb.GetDefinition(UInt32Value(value=0)).du_definition],
                fivegc_array=[fivegc],
            )
            ping(
                ue_attach_info_dict=ue_attach_info_dict,
                fivegc=fivegc,
                ping_count=ping_count,
                ping_interval=ping_interval,
            )
    except Failed as err:
        if not ims_mode or ims_mode == "enabled":
            raise err from None

    if ims_mode:
        validate_ue_registered_via_ims(ue_stub_array=ue_array if ims_mode == "enabled" else tuple(), core=fivegc)

    # final stop
    stop(
        ue_array=ue_array,
        gnb_array=[gnb],
        fivegc_array=[fivegc],
        retina_data=retina_data,
        gnb_stop_timeout=gnb_stop_timeout,
        log_search=log_search,
        ue_stop_timeout=ue_stop_timeout,
        warning_as_errors=warning_as_errors,
    )
