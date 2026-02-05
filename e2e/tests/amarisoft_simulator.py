#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Test ping
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Generator

import pytest
import yaml
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData
from retina.launcher.public import UInt32Value
from retina.launcher.utils import configure_artifacts
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import GNBStub
from retina.protocol.ue_pb2_grpc import UEStub

from .steps.configuration import set_config_files
from .steps.stub import start_network, stop, ue_start


@dataclass
class AmarisoftSimTestDefinition:
    """
    Test definition for Amarisoft simulator tests
    """

    name: str
    ue_config: list[str]
    gnb_config: list[str]
    core_config: list[str]


def load_tests(template_name: str) -> Generator[AmarisoftSimTestDefinition, None, None]:
    """
    Load test definitions from YAML files
    """
    suites_dir = Path(__file__).parent / "suites"
    for test_definition_file in suites_dir.rglob("*.y*ml"):
        with open(test_definition_file, "r", encoding="UTF-8") as file:
            test_definition_raw = yaml.safe_load(file)
        for test_name, test_declaration in test_definition_raw.items():
            if test_declaration.get("template", "") == template_name:
                file_path = test_definition_file.relative_to(suites_dir).with_suffix("")
                test_id = f"{str(file_path).replace('/', '::')}::{test_name}"
                yield AmarisoftSimTestDefinition(
                    name=test_id,
                    gnb_config=test_declaration.get("gnb_config", []),
                    ue_config=test_declaration.get("ue_config", []),
                    core_config=test_declaration.get("core_config", []),
                )


@pytest.mark.parametrize(
    "test_definition",
    [pytest.param(tdef, id=tdef.name) for tdef in load_tests(Path(__file__).stem)],
)
# pylint: disable=too-many-arguments,too-many-positional-arguments
def test_gnb(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    ue: UEStub,
    gnb: GNBStub,
    fivegc: FiveGCStub,
    test_definition: AmarisoftSimTestDefinition,
):
    """Template test function for Amarisoft simulator tests"""

    configure_artifacts(
        retina_data=retina_data,
        always_download_artifacts=True,
    )

    set_config_files(
        retina_manager=retina_manager,
        retina_data=retina_data,
        ue_config_files=test_definition.ue_config,
        gnb_config_files=test_definition.gnb_config,
        core_config_files=test_definition.core_config,
    )

    start_network(
        ue_array=(ue,),
        gnb_array=(gnb,),
        fivegc=fivegc,
    )

    ue_start(
        ue_array=(ue,),
        du_definition=[gnb.GetDefinition(UInt32Value(value=0))],
        fivegc=fivegc,
    )

    logging.info("Setup Completed")

    sleep(30)

    stop(
        ue_array=(ue,),
        gnb_array=(gnb,),
        fivegc=fivegc,
        retina_data=retina_data,
        warning_as_errors=True,
    )
