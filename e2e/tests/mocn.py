# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Multi Core Network Test
"""

import ipaddress
from typing import Callable, Tuple

from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import CriteriaTable
from retina.launcher.utils import configure_artifacts
from retina.protocol.base_pb2 import Subscriber
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import GNBStub
from retina.protocol.ue_pb2 import UEAttachedInfo
from retina.protocol.ue_pb2_grpc import UEStub

from .steps.configuration import set_config_files
from .steps.stub import (
    fivegc_start,
    gnb_start,
    ping_start,
    ping_wait_until_finish,
    stop,
    ue_start,
)
from .steps.test_loader import load_tests, RetinaTestDefinition


@load_tests
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def test(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    criteria: CriteriaTable,
    test_definition: RetinaTestDefinition,
    ue: UEStub,
    gnb: GNBStub,
    fivegc_multiple: Callable[[int], Tuple[FiveGCStub, ...]],
):
    """
    Multi Core Network Test
    """

    core1, core2 = fivegc_multiple(2)

    # Apply configurations
    configure_artifacts(
        retina_data=retina_data,
        always_download_artifacts=True,
    )
    set_config_files(retina_manager=retina_manager, retina_data=retina_data, test_definition=test_definition)

    # Apply criteria
    for criteria_id, criteria_expected_value in test_definition.criteria.items():
        criteria.add_criteria(criteria_id, criteria_expected_value)

    # Start the cores and gnb
    core1_def = fivegc_start(core1)
    core2_def = fivegc_start(core2)

    gnb_def = gnb_start(
        gnb,
        ue_definition=ue.GetDefinition(Empty()),
        fivegc_definition_array=(core1_def, core2_def),
    )

    # Register UE in both core
    ue_subscriber: Subscriber = ue.GetDefinition(Empty()).subscriber
    for idx, core in enumerate([core1, core2]):
        if len(test_definition.core.items) > idx and "slices" in test_definition.core.items[idx].parameters:
            ue_subscriber.sd = str(test_definition.core.items[idx].parameters["slices"][0])
        core.AddUESubscriber(ue_subscriber)

    # Start UE and waits until attach
    ue_start(
        ue_array=(ue,),
        du_definition=(gnb_def.du_definition,),
        fivegc_array=(core1, core2),
    )
    ue.WaitUntilAttached(UInt32Value(value=10))

    # Generate some traffic
    ping_tasks = []
    ping_tasks.extend(
        ping_start(
            ue_attach_info_dict={
                ue: UEAttachedInfo(
                    ipv4_gateway=core1_def.tun_ip,
                    ipv4=str(ipaddress.ip_address(core1_def.tun_ip) + 1),
                )
            },
            fivegc=core1,
            ping_count=10,
        )
    )
    ping_tasks.extend(
        ping_start(
            ue_attach_info_dict={
                ue: UEAttachedInfo(
                    ipv4_gateway=core2_def.tun_ip,
                    ipv4=str(ipaddress.ip_address(core2_def.tun_ip) + 1),
                )
            },
            fivegc=core2,
            ping_count=10,
        )
    )
    ping_wait_until_finish(ping_tasks)

    # Stop and validate criteria
    try:
        stop(
            ue_array=(ue,),
            gnb_array=(gnb,),
            fivegc_array=(core1, core2),
            retina_data=retina_data,
            warning_as_errors=False,
        )
    finally:
        criteria.validate()
