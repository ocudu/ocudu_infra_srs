# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Paging Tests
"""

import logging
from time import sleep
from typing import Callable, Tuple

from google.protobuf.wrappers_pb2 import UInt32Value
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import CriteriaTable
from retina.launcher.utils import configure_artifacts
from retina.protocol import FiveGCClient, GNBClient, UEClient

from .steps.configuration import set_config_files
from .steps.stub import start_network, stop, ue_start_and_attach
from .steps.test_loader import load_tests, RetinaTestDefinition
from .steps.traffic import ping, ping_from_5gc


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue_multiple: Callable[[int], Tuple[UEClient, ...]],
    gnb: GNBClient,
    fivegc: FiveGCClient,
):
    """Template test function for paging: the UE is left idle and the core pages it with a ping"""

    parameters = test_definition.parameters
    ue_array = ue_multiple(1)
    ping_count = parameters.get("ping_count", 10)
    # Several times the inactivity timer, so that the background traffic of the phone does not keep
    # the UE connected until the end of the wait
    idle_duration = parameters.get("idle_duration", 15)

    set_config_files(retina_manager=retina_manager, retina_data=retina_data, test_definition=test_definition)
    configure_artifacts(retina_data=retina_data, always_download_artifacts=True)

    for criteria_id, criteria_expected_value in test_definition.criteria.items():
        criteria.add_criteria(criteria_id, criteria_expected_value)

    try:
        logging.info("Paging Test")
        start_network(ue_array=ue_array, gnb_array=[gnb], fivegc_array=[fivegc])
        ue_attach_info_dict = ue_start_and_attach(
            ue_array=ue_array,
            du_definition=[gnb.GetDefinition(UInt32Value(value=0)).du_definition],
            fivegc_array=[fivegc],
        )
        ping(ue_attach_info_dict=ue_attach_info_dict, fivegc=fivegc, ping_count=ping_count)
        sleep(idle_duration)
        ping_from_5gc(ue_attach_info_dict=ue_attach_info_dict, fivegc=fivegc, ping_count=ping_count)
        stop(
            ue_array=ue_array,
            gnb_array=[gnb],
            fivegc_array=[fivegc],
            retina_data=retina_data,
            warning_as_errors=False,
        )
    finally:
        criteria.validate()
