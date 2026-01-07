#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Orchestration fixtures
"""

import logging
from getpass import getuser
from typing import Dict, Generator

import pytest
import yaml
from retina.orchestrator.orchestration_network import OrchestratorManager

from retina.launcher.cmd_args import RetinaRequest


@pytest.fixture
def orchestration(
    retina_request: RetinaRequest,
) -> Generator[Dict, None, None]:
    """
    Call retina orchestration for the request
    """
    if retina_request.request:
        try:
            orch_manager = OrchestratorManager(is_incluster=retina_request.in_cluster)
            _, _, orch_network = orch_manager.create_infrastructure(
                request_path=retina_request.request,
                user_name=_get_retina_user(),
                timeout=retina_request.pod_timeout,
            )
            yield orch_network
        finally:
            try:
                orch_manager.delete_orchestration_network()
            except UnboundLocalError:
                pass
            except Exception as err:  # pylint: disable=broad-exception-caught
                logging.exception(err)
    else:
        with open(
            retina_request.testbed,
            encoding="utf-8",
        ) as file:
            orch_network = yaml.load(file, yaml.FullLoader)
        yield orch_network


def _get_retina_user():
    """
    Get current user name
    """
    user_name = getuser()
    if not user_name:
        user_name = "retina_user"
    return user_name
