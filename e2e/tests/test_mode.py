# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Validate Test Mode
"""

import logging
import tempfile
from pathlib import Path
from time import sleep
from typing import List, Optional

import pytest
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from pytest import mark
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import CriteriaTable
from retina.launcher.utils import configure_artifacts
from retina.protocol import FiveGCClient, GNBClient
from retina.protocol.base_pb2 import FiveGCDefinition, GNBDefinition, Metrics, PLMN, StartInfo, UEDefinition
from retina.protocol.gnb_pb2 import GNBStartInfo

from .steps.configuration import set_config_files
from .steps.stub import fivegc_start, gnb_start, GNB_STARTUP_TIMEOUT, handle_start_error, stop
from .steps.test_loader import load_tests, RetinaTestDefinition


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    gnb: GNBClient,
    fivegc: FiveGCClient,
):
    """
    Template test function for the gNB test mode, where the gNB creates the test UEs itself: it
    runs for the duration given by the parameters of the test with no UE simulator attached.
    """
    plmn = PLMN(mcc="001", mnc="01")
    duration = test_definition.parameters.get("duration", 5 * 60)

    set_config_files(retina_manager=retina_manager, retina_data=retina_data, test_definition=test_definition)
    configure_artifacts(retina_data=retina_data, always_download_artifacts=True)

    for criteria_id, criteria_expected_value in test_definition.criteria.items():
        criteria.add_criteria(criteria_id, criteria_expected_value)

    try:
        fivegc_definition = fivegc_start(fivegc, plmn=plmn)

        # There is no UE agent, so the gNB gets its own zmq endpoints as the UE definition
        gnb_definition: GNBDefinition = gnb.GetDefinition(UInt32Value(value=0))
        gnb_start(
            gnb,
            plmn=plmn,
            ue_definition=UEDefinition(
                zmq_ip=gnb_definition.du_definition.zmq_ip,
                zmq_port_array=gnb_definition.du_definition.zmq_port_array,
            ),
            fivegc_definition_array=[fivegc_definition],
        )

        logging.info("Running Test Mode for %s seconds", duration)
        sleep(duration)

        stop(
            ue_array=tuple(),
            gnb_array=[gnb],
            fivegc_array=[fivegc],
            retina_data=retina_data,
            warning_as_errors=False,
        )
    finally:
        criteria.validate()


@mark.test_mode_acc100
def test_ru_acc100(
    # Retina
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    # Clients
    gnb: GNBClient,
):
    """
    Run gnb in test mode ru dummy.
    """
    _test_ru(
        retina_manager=retina_manager,
        retina_data=retina_data,
        gnb=gnb,
        ru_config="config_ru_acc100.yml",
        min_dl_bitrate=1e6,
        warning_allowlist=[
            "Resource grid with identifier",
            "Could not enqueue PDCCH",
            "received late DL request from slot",
        ],
    )


@mark.test_mode
def test_ru(
    # Retina
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    # Clients
    gnb: GNBClient,
):
    """
    Run gnb in test mode ru dummy.
    """
    _test_ru(retina_manager=retina_manager, retina_data=retina_data, gnb=gnb, ru_config="config_ru.yml")


@mark.test_mode
def test_ru_10cell_50ue(
    # Retina
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    # Clients
    gnb: GNBClient,
):
    """
    Run gnb in test mode ru dummy.
    """
    _test_ru(
        retina_manager=retina_manager,
        retina_data=retina_data,
        gnb=gnb,
        ru_config="config_ru_10cell_50ue.yml",
        duration=10 * 60,
        warning_as_errors=False,
    )


@mark.test_mode_not_crash
def test_ru_not_crash(
    # Retina
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    # Clients
    gnb: GNBClient,
):
    """
    Run gnb with sanitizers in test mode ru dummy.
    It ignores warnings and KOs, so it will fail if the gnb+sanitizer fails
    """
    _test_ru(
        retina_manager=retina_manager,
        retina_data=retina_data,
        gnb=gnb,
        ru_config="config_ru.yml",
        gnb_stop_timeout=150,
        warning_as_errors=False,
        fail_if_kos=False,
    )


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _test_ru(
    *,  # This enforces keyword-only arguments
    # Retina
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    # Clients
    gnb: GNBClient,
    # Test
    ru_config,
    nof_ant: int = 4,
    duration: int = 5 * 60,
    # Test extra params
    always_download_artifacts: bool = True,
    gnb_startup_timeout: int = GNB_STARTUP_TIMEOUT,
    gnb_stop_timeout: int = 0,
    # Criteria
    log_search: bool = True,
    warning_as_errors: bool = True,
    warning_allowlist: Optional[List[str]] = None,
    fail_if_kos: bool = True,
    min_dl_bitrate: float = 1,
    min_ul_bitrate: float = 1,
):  # pylint: disable=too-many-locals
    # Configuration
    with tempfile.NamedTemporaryFile(mode="w+") as tmp_file:
        tmp_file.write(" ")  # Make it not empty to overwrite default one
        tmp_file.flush()
        retina_data.test_config = {
            "gnb": {
                "parameters": {
                    "gnb_id": 1,
                    "log_level": "warning",
                    "pcap": False,
                    "nof_antennas_dl": nof_ant,
                    "nof_antennas_ul": nof_ant,
                    "warning_allowlist": warning_allowlist if warning_allowlist is not None else [],
                },
                "templates": {
                    "cu": str(Path(__file__).joinpath(f"../test_mode/{ru_config}").resolve()),
                    "du": tmp_file.name,
                    "ru": tmp_file.name,
                },
            },
        }
        retina_manager.parse_configuration(retina_data.test_config)
        retina_manager.push_all_config()

    configure_artifacts(
        retina_data=retina_data,
        always_download_artifacts=always_download_artifacts,
    )

    # GNB Start
    with handle_start_error(name=f"GNB [{id(gnb)}]"):
        gnb.Start(
            GNBStartInfo(
                plmn=PLMN(mcc="001", mnc="01"),
                ue_definition=UEDefinition(zmq_port_array=tuple(range(nof_ant))),
                fivegc_definition=[FiveGCDefinition(amf_ip="127.0.0.1", amf_port=38412)],
                start_info=StartInfo(
                    timeout=gnb_startup_timeout,
                    post_commands=("cu_cp amf --no_core 1",),
                ),
            )
        )

    logging.info("Running Test Mode for %s seconds", duration)
    sleep(duration)

    # Stop
    stop(
        ue_array=tuple(),
        gnb_array=[gnb],
        fivegc_array=None,
        retina_data=retina_data,
        gnb_stop_timeout=gnb_stop_timeout,
        log_search=log_search,
        warning_as_errors=warning_as_errors,
        fail_if_kos=fail_if_kos,
    )

    metrics: Metrics = gnb.GetMetrics(Empty())
    if metrics.aggregate.dl_bitrate < min_dl_bitrate:
        pytest.fail(f"Low DL Bitrate: {metrics.aggregate.dl_bitrate} [< {min_dl_bitrate}]")
    if metrics.aggregate.ul_bitrate < min_ul_bitrate:
        pytest.fail(f"Low UL Bitrate: {metrics.aggregate.ul_bitrate} [< {min_ul_bitrate}]")


@mark.test_mode_many_ues
# pylint: disable=too-many-locals
def test_mode_many_ues(
    # Retina
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    # Clients
    gnb: GNBClient,
    # Test
    ru_config="config_ru_800_ues.yml",
    nof_ant: int = 4,
    duration: int = 5 * 60,
    # Test extra params
    always_download_artifacts: bool = True,
    gnb_startup_timeout: int = GNB_STARTUP_TIMEOUT,
    gnb_stop_timeout: int = 0,
    log_search: bool = True,
    warning_as_errors: bool = False,
    fail_if_kos: bool = False,
    extra_cli_config: str = "metrics --enable_log=true",
):
    """
    Run gnb in test mode ru dummy and 800 UEs.
    It fails if less than 800 UEs are connected or the total bitrate is below the expected threshold
    """
    with tempfile.NamedTemporaryFile(mode="w+") as tmp_file:
        tmp_file.write(" ")  # Make it not empty to overwrite default one
        tmp_file.flush()
        retina_data.test_config = {
            "gnb": {
                "parameters": {
                    "gnb_id": 1,
                    "log_level": "warning",
                    "pcap": False,
                    "nof_antennas_dl": nof_ant,
                    "nof_antennas_ul": nof_ant,
                },
                "templates": {
                    "cu": str(Path(__file__).joinpath(f"../test_mode/{ru_config}").resolve()),
                    "du": tmp_file.name,
                    "ru": tmp_file.name,
                },
            },
        }
        retina_manager.parse_configuration(retina_data.test_config)
        retina_manager.push_all_config()

    configure_artifacts(
        retina_data=retina_data,
        always_download_artifacts=always_download_artifacts,
    )

    # GNB Start
    with handle_start_error(name=f"GNB [{id(gnb)}]"):
        gnb.Start(
            GNBStartInfo(
                plmn=PLMN(mcc="001", mnc="01"),
                ue_definition=UEDefinition(zmq_port_array=tuple(range(nof_ant))),
                fivegc_definition=[FiveGCDefinition(amf_ip="127.0.0.1", amf_port=38412)],
                start_info=StartInfo(
                    timeout=gnb_startup_timeout,
                    post_commands=(f"cu_cp amf --no_core 1 {extra_cli_config}",),
                ),
            )
        )

    logging.info("Running Test Mode for %s seconds", duration)
    sleep(duration)

    # Stop
    stop(
        ue_array=tuple(),
        gnb_array=[gnb],
        fivegc_array=None,
        retina_data=retina_data,
        gnb_stop_timeout=gnb_stop_timeout,
        log_search=log_search,
        warning_as_errors=warning_as_errors,
        fail_if_kos=fail_if_kos,
    )
