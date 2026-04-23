# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Steps related with stubs / resources
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator

import jsonschema
import pytest
import yaml

from .. import criterias as _

_TEST_DEFINITION_SCHEMA: Dict = {
    "$defs": {
        "item_config": {
            "type": "object",
            "properties": {
                "config": {"type": "array", "items": {"type": "string"}},
                "parameters": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "node_type_definition": {
            "type": "object",
            "properties": {
                "config": {"type": "array", "items": {"type": "string"}},
                "parameters": {"type": "object"},
                "items": {"type": "array", "items": {"$ref": "#/$defs/item_config"}},
            },
            "additionalProperties": False,
        },
    },
    "type": "object",
    "properties": {
        "template": {"type": "string"},
        "request": {"type": "string"},
        "feature_ids": {"type": "array", "items": {"type": "string"}},
        "criteria": {"type": "object", "additionalProperties": {}},
        "ue": {"$ref": "#/$defs/node_type_definition"},
        "cu": {"$ref": "#/$defs/node_type_definition"},
        "du": {"$ref": "#/$defs/node_type_definition"},
        "gnb": {"$ref": "#/$defs/node_type_definition"},
        "core": {"$ref": "#/$defs/node_type_definition"},
    },
    "additionalProperties": False,
}


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
    # Configs
    ue: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    cu: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    du: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    gnb: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)
    core: RetinaNodeTypeDefinition = field(default_factory=RetinaNodeTypeDefinition)

    @classmethod
    def from_dict(cls, name: str, data: Dict) -> "RetinaTestDefinition":
        """Create object from dictionary with type"""
        try:
            jsonschema.validate(data, _TEST_DEFINITION_SCHEMA)
            instance = cls(
                name=name,
                retina_request=data.get("request", "zmq_mme"),
                feature_ids=data.get("feature_ids", []),
                criteria=data.get("criteria", {}),
                ue=RetinaNodeTypeDefinition.from_dict(data.get("ue", {})),
                cu=RetinaNodeTypeDefinition.from_dict(data.get("cu", {})),
                du=RetinaNodeTypeDefinition.from_dict(data.get("du", {})),
                gnb=RetinaNodeTypeDefinition.from_dict(data.get("gnb", {})),
                core=RetinaNodeTypeDefinition.from_dict(data.get("core", {})),
            )
        except jsonschema.ValidationError as e:
            raise ValueError(f"Invalid test definition '{name}': {e.message}") from e
        all_configs = []
        for cfg_file in instance.ue.config:
            all_configs.append(Path(__file__).parent.parent / "configs" / "ue" / cfg_file)
        for cfg_file in instance.cu.config:
            all_configs.append(Path(__file__).parent.parent / "configs" / "cu" / cfg_file)
        for cfg_file in instance.du.config:
            all_configs.append(Path(__file__).parent.parent / "configs" / "du" / cfg_file)
        for cfg_file in instance.gnb.config:
            all_configs.append(Path(__file__).parent.parent / "configs" / "gnb" / cfg_file)
        for cfg_file in instance.core.config:
            all_configs.append(Path(__file__).parent.parent / "configs" / "core" / cfg_file)
        for cfg_path in all_configs:
            if not cfg_path.exists():
                raise ValueError(f"{cfg_path} config file does not exist.")
        return instance


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
                marks=[getattr(pytest.mark, item) for item in (tdef.retina_request, *tdef.feature_ids)],
            )
            for tdef in _parse_test_definitions(func.__module__.split(".")[-1] + "." + func.__qualname__)
        ],
        indirect=["retina_request"],
    )(func)
