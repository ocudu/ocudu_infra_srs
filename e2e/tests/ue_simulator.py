# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Test ping
"""

from contextlib import suppress
from time import sleep

import grpc
from google.protobuf.empty_pb2 import Empty
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import Criteria
from retina.launcher.public import UInt32Value
from retina.launcher.utils import configure_artifacts
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import GNBStub
from retina.protocol.ue_pb2_grpc import UEStub

from .steps.configuration import set_config_files
from .steps.stub import start_network, stop, ue_start
from .steps.test_loader import load_tests, RetinaTestDefinition


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: Criteria,
    test_definition: RetinaTestDefinition,
    ue: UEStub,
    gnb: GNBStub,
    fivegc: FiveGCStub,
):
    """Template test function for Amarisoft simulator tests"""

    configure_artifacts(
        retina_data=retina_data,
        always_download_artifacts=True,
    )

    test_definition.ue.parameters["ue_simulator_mode"] = True
    set_config_files(retina_manager=retina_manager, retina_data=retina_data, test_definition=test_definition)

    for criteria_id, criteria_expected_value in test_definition.criteria.items():
        criteria.add_criteria(criteria_id, criteria_expected_value)

    start_network(
        ue_array=(ue,),
        gnb_array=(gnb,),
        fivegc_array=[fivegc],
    )

    ue_start(
        ue_array=(ue,),
        du_definition=[gnb.GetDefinition(UInt32Value(value=0))],
        fivegc=fivegc,
    )

    # Wait until UE stops
    with suppress(grpc.RpcError):
        while True:
            ue.GetMessages(Empty())
            sleep(1)

    try:
        stop(
            ue_array=(ue,),
            gnb_array=(gnb,),
            fivegc_array=[fivegc],
            retina_data=retina_data,
            warning_as_errors=False,
        )
    finally:
        criteria.validate()
