# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Test ping
"""

from _pytest.outcomes import Failed
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.criteria import CriteriaTable
from retina.launcher.utils import configure_artifacts
from retina.protocol import FiveGCClient, GNBClient, UEClient

from .steps.configuration import set_config_files
from .steps.stub import (
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
    Template test function for pings between the UE and the core. The number of pings, the interval
    between them and how many times the UE is stopped and attached again come from the parameters
    of the test. The UE is validated in IMS when the core config sets an IMS mode
    """

    parameters = test_definition.parameters
    ping_count = parameters.get("ping_count", 10)
    ping_interval = parameters.get("ping_interval", 1.0)
    ims_mode = test_definition.core.parameters.get("ims_mode", "")
    ue_array = (ue,)

    set_config_files(retina_manager=retina_manager, retina_data=retina_data, test_definition=test_definition)
    configure_artifacts(retina_data=retina_data, always_download_artifacts=True)

    for criteria_id, criteria_expected_value in test_definition.criteria.items():
        criteria.add_criteria(criteria_id, criteria_expected_value)

    try:
        start_network(ue_array=ue_array, gnb_array=[gnb], fivegc_array=[fivegc])

        try:
            # One ping per attach, stopping the UE in between when the test asks for re-attaches
            for attach in range(parameters.get("reattach_count", 0) + 1):
                if attach:
                    ue_stop(ue_array=ue_array, retina_data=retina_data)
                ping(
                    ue_attach_info_dict=ue_start_and_attach(
                        ue_array=ue_array,
                        du_definition=[gnb.GetDefinition(UInt32Value(value=0)).du_definition],
                        fivegc_array=[fivegc],
                    ),
                    fivegc=fivegc,
                    ping_count=ping_count,
                    ping_interval=ping_interval,
                )
        except Failed:
            # The traffic is expected to fail when the UE does not register in IMS
            if not ims_mode or ims_mode == "enabled":
                raise

        if ims_mode:
            validate_ue_registered_via_ims(ue_stub_array=ue_array if ims_mode == "enabled" else tuple(), core=fivegc)

        stop(
            ue_array=ue_array,
            gnb_array=[gnb],
            fivegc_array=[fivegc],
            retina_data=retina_data,
            warning_as_errors=False,
        )
    finally:
        criteria.validate()
