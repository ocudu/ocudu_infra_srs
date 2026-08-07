# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Validate Test Mode
"""

import logging
from time import sleep

from google.protobuf.wrappers_pb2 import UInt32Value
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import CriteriaTable
from retina.launcher.utils import configure_artifacts
from retina.protocol import FiveGCClient, GNBClient
from retina.protocol.base_pb2 import FiveGCDefinition, GNBDefinition, PLMN, UEDefinition

from .steps.configuration import set_config_files
from .steps.stub import fivegc_start, gnb_start, stop
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


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb_no_core(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    gnb: GNBClient,
):
    """
    Template test function for the gNB test mode with a dummy RU and no core: the gNB creates the
    test UEs itself and generates their traffic, so it runs alone for the duration given by the
    parameters of the test.
    """
    duration = test_definition.parameters.get("duration", 5 * 60)
    nof_antennas = max(
        test_definition.gnb.parameters.get("nof_antennas_dl", 1),
        test_definition.gnb.parameters.get("nof_antennas_ul", 1),
    )

    set_config_files(
        retina_manager=retina_manager,
        retina_data=retina_data,
        test_definition=test_definition,
        overwrite_radio=True,  # The test configures the dummy RU, so the radio of the testbed is not used
    )
    configure_artifacts(retina_data=retina_data, always_download_artifacts=True)

    for criteria_id, criteria_expected_value in test_definition.criteria.items():
        criteria.add_criteria(criteria_id, criteria_expected_value)

    try:
        gnb_start(
            gnb,
            plmn=PLMN(mcc="001", mnc="01"),
            ue_definition=UEDefinition(zmq_port_array=tuple(range(nof_antennas))),
            fivegc_definition_array=[FiveGCDefinition(amf_ip="127.0.0.1", amf_port=38412)],
            post_cmd=("cu_cp amf --no_core 1",),
        )

        logging.info("Running Test Mode for %s seconds", duration)
        sleep(duration)

        stop(
            ue_array=tuple(),
            gnb_array=[gnb],
            fivegc_array=None,
            retina_data=retina_data,
            warning_as_errors=False,
        )
    finally:
        criteria.validate()
