# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Test ping
"""

from contextlib import suppress
from time import sleep
from typing import Optional, Sequence

import grpc
from google.protobuf.empty_pb2 import Empty
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import CriteriaTable
from retina.launcher.public import UInt32Value
from retina.launcher.utils import configure_artifacts
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import CUCPStub, CUStub, CUUPStub, DUStub, GNBStub
from retina.protocol.ue_pb2_grpc import UEStub

from .steps.configuration import set_config_files
from .steps.stub import start_network, stop, ue_start
from .steps.test_loader import load_tests, RetinaTestDefinition


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEStub,
    gnb: GNBStub,
    fivegc: FiveGCStub,
):
    """Template test function for UE simulator + gNB + Core"""
    _ue_simulator(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue=ue,
        gnb_array=[gnb],
        fivegc_array=[fivegc],
    )


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_2gnb(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEStub,
    gnb_multiple,
    fivegc: FiveGCStub,
):
    """Template test function for UE simulator + 2 gNB + Core"""
    _ue_simulator(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue=ue,
        gnb_array=gnb_multiple(2),
        fivegc_array=[fivegc],
    )


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb_2core(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEStub,
    gnb: GNBStub,
    fivegc_multiple,
):
    """Template test function for UE simulator + GNB + 2 Core"""
    _ue_simulator(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue=ue,
        gnb_array=[gnb],
        fivegc_array=fivegc_multiple(2),
    )


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_cu_2du(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEStub,
    cu: CUStub,
    du_multiple,
    fivegc: FiveGCStub,
):
    """Template test function for UE simulator + CU + 2 DU + Core"""
    _ue_simulator(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue=ue,
        cu=cu,
        du_array=du_multiple(2),
        fivegc_array=[fivegc],
    )


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_cucp_cuup(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEStub,
    cu_cp: CUCPStub,
    cu_up: CUUPStub,
    du: DUStub,
    fivegc: FiveGCStub,
):
    """Template test function for UE simulator + CUCP + 2 CUUP + DU + Core"""
    _ue_simulator(
        retina_manager=retina_manager,
        retina_data=retina_data,
        criteria=criteria,
        test_definition=test_definition,
        ue=ue,
        cu_cp=cu_cp,
        cu_up_array=[cu_up],
        du_array=[du],
        fivegc_array=[fivegc],
    )


def _ue_simulator(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEStub,
    fivegc_array: Sequence[FiveGCStub],
    cu: Optional[CUStub] = None,
    cu_cp: Optional[CUCPStub] = None,
    cu_up_array: Optional[Sequence[CUUPStub]] = None,
    du_array: Optional[Sequence[DUStub]] = None,
    gnb_array: Optional[Sequence[GNBStub]] = None,
):  # pylint: disable=too-many-arguments,too-many-positional-arguments

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
        cu=cu,
        cu_cp=cu_cp,
        cu_up_array=cu_up_array,
        gnb_array=gnb_array,
        du_array=du_array,
        fivegc_array=fivegc_array,
    )

    if gnb_array:
        du_definition = [gnb.GetDefinition(UInt32Value(value=idx)).du_definition for idx, gnb in enumerate(gnb_array)]
    elif du_array:
        du_definition = [du.GetDefinition(UInt32Value(value=idx)) for idx, du in enumerate(du_array)]
    else:
        raise ValueError("GNB or DU is required")

    ue_start(
        ue_array=(ue,),
        du_definition=du_definition,
        fivegc_array=fivegc_array,
    )

    # Wait until UE stops
    with suppress(grpc.RpcError):
        while True:
            ue.GetMessages(Empty())
            sleep(5)

    try:
        stop(
            ue_array=(ue,),
            cu=cu,
            cu_cp=cu_cp,
            cu_up_array=cu_up_array,
            du_array=du_array,
            gnb_array=gnb_array,
            fivegc_array=fivegc_array,
            retina_data=retina_data,
            warning_as_errors=False,
        )
    finally:
        criteria.validate()
