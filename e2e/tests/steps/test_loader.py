# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Steps related with stubs / resources
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator

import pytest
import yaml

from .. import criterias as _

# Testbed groups a retina request can belong to. Every test case is marked with the group of
# its request on top of the request itself, so that every test case of a testbed can be
# selected with a single marker (see PIPELINES in e2e/scripts/generate_pipelines.py). Every
# group in use has to be declared in the markers list of e2e/pyproject.toml.
RETINA_REQUEST_GROUPS = ("android", "interop", "rf", "s72", "test_mode", "viavi", "zmq")


def get_request_group(retina_request: str) -> str:
    """
    Gets the testbed group of the given retina request, or the request itself if it is not
    part of any of the known groups.
    """

    for group in RETINA_REQUEST_GROUPS:
        if retina_request == group or retina_request.startswith(f"{group}_"):
            return group

    return retina_request


@dataclass
class RetinaItemConfig:
    """
    Configuration for a Retina Item
    """

    config: list[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> "RetinaItemConfig":
        """Create object from dictionary with type"""
        return cls(
            config=data.get("config", []),
            parameters=data.get("parameters", {}),
        )


@dataclass
class RetinaNodeTypeDefinition(RetinaItemConfig):
    """
    Item Definition
    """

    items: list[RetinaItemConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict) -> "RetinaNodeTypeDefinition":
        """Create object from dictionary with type"""
        return cls(
            config=data.get("config", []),
            parameters=data.get("parameters", {}),
            items=[RetinaItemConfig.from_dict(i) for i in data.get("items", [])],
        )


@dataclass
class RetinaTestDefinition:  # pylint: disable=too-many-instance-attributes
    """
    Retina Test definition
    """

    name: str
    retina_request: str
    feature_ids: list[str]
    criteria: Dict[str, float]
    parameters: Dict[str, Any] = field(default_factory=dict)
    # Configs
    ue: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    cu: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    cu_cp: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    cu_up: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    du: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    gnb: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    core: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)

    @classmethod
    def from_dict(cls, name: str, data: Dict) -> "RetinaTestDefinition":
        """Create object from dictionary with type"""
        return cls(
            name=name,
            retina_request=data.get("request", "zmq_mme"),
            feature_ids=data.get("feature_ids", []),
            criteria=data.get("criteria", {}),
            parameters=data.get("parameters", {}),
            ue=RetinaNodeTypeDefinition.from_dict(data.get("ue", {})),
            cu=RetinaNodeTypeDefinition.from_dict(data.get("cu", {})),
            cu_cp=RetinaNodeTypeDefinition.from_dict(data.get("cu_cp", {})),
            cu_up=RetinaNodeTypeDefinition.from_dict(data.get("cu_up", {})),
            du=RetinaNodeTypeDefinition.from_dict(data.get("du", {})),
            gnb=RetinaNodeTypeDefinition.from_dict(data.get("gnb", {})),
            core=RetinaNodeTypeDefinition.from_dict(data.get("core", {})),
        )


def _parse_test_definitions(template_name: str) -> Generator[RetinaTestDefinition, None, None]:
    suites_dir = Path(__file__).parent.parent / "suites"
    for test_definition_file in suites_dir.rglob("*.y*ml"):
        with open(test_definition_file, "r", encoding="UTF-8") as file:
            test_definition_raw = yaml.safe_load(file)
        if not test_definition_raw:
            continue
        for test_name, test_declaration in test_definition_raw.items():
            if test_declaration.get("template", "") == template_name:
                file_path = test_definition_file.relative_to(suites_dir).with_suffix("")
                test_id = f"{str(file_path).replace('/', '.')}.{test_name}"
                yield RetinaTestDefinition.from_dict(test_id, test_declaration)


def load_tests(func: Callable):
    """
    Load test definitions from YAML files
    """
    return pytest.mark.parametrize(
        "test_definition,retina_request",
        [
            pytest.param(
                tdef,
                f"retina_requests/{tdef.retina_request}.yml",
                id=tdef.name,
                # dict.fromkeys keeps the order and drops the group when it is the request itself
                marks=[
                    getattr(pytest.mark, item)
                    for item in dict.fromkeys(
                        (tdef.retina_request, get_request_group(tdef.retina_request), *tdef.feature_ids)
                    )
                ],
            )
            for tdef in _parse_test_definitions(func.__module__.split(".")[-1] + "." + func.__qualname__)
        ],
        indirect=["retina_request"],
    )(func)
