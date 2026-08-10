# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Configuration related steps
"""

import contextlib
import tempfile
from pathlib import Path
from typing import Dict, NamedTuple, Sequence

from retina.client.core import storage
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData

from .test_loader import RetinaNodeTypeDefinition, RetinaTestDefinition


class _NodeConfig(NamedTuple):
    attr: str  # attribute on RetinaTestDefinition
    config_folder: str  # Config folder
    templates: list  # template names expected by the retina API
    ru_template: str = ""  # template the agent renders from the radio reserved for the testbed


_NODE_CONFIGS: Dict[storage.NodeTypeEnum, _NodeConfig] = {
    storage.NodeTypeEnum.UE: _NodeConfig("ue", "ue", ["ue"]),
    storage.NodeTypeEnum.CU: _NodeConfig("cu", "gnb", ["cu", "qos"]),
    storage.NodeTypeEnum.CU_CP: _NodeConfig("cu_cp", "gnb", ["cu", "qos"]),
    storage.NodeTypeEnum.CU_UP: _NodeConfig("cu_up", "gnb", ["cu", "qos"]),
    storage.NodeTypeEnum.DU: _NodeConfig("du", "gnb", ["du", "qos"], "ru"),
    storage.NodeTypeEnum.GNB: _NodeConfig("gnb", "gnb", ["cu", "du", "qos"], "ru"),
    storage.NodeTypeEnum.FIVEGC: _NodeConfig("core", "core", ["core"]),
}


def set_config_files(
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    test_definition: RetinaTestDefinition,
    overwrite_radio: bool = False,
):
    """
    Overwrite default config files with the provided ones. With overwrite_radio, the radio config the
    agent renders from the resources reserved for the testbed is emptied too, so that the config
    files of the test are the ones defining the radio.
    """
    with contextlib.ExitStack() as stack:
        retina_data.test_config = {}

        for node_type, node_cfg in _NODE_CONFIGS.items():
            item: RetinaNodeTypeDefinition = getattr(test_definition, node_cfg.attr)
            if not item.config and not item.parameters and not item.items:
                continue

            blank_templates = (node_cfg.ru_template,) if overwrite_radio and node_cfg.ru_template else ()

            retina_data.test_config[node_type.value] = {}
            if item.config:
                retina_data.test_config[node_type.value]["templates"] = _build_templates(
                    stack, node_cfg, item.config, blank_templates
                )
            if item.parameters:
                retina_data.test_config[node_type.value]["parameters"] = item.parameters
            if item.items:
                retina_data.test_config[node_type.value]["node_list"] = [
                    {
                        "name": storage.clients[node_type][i].name,
                        **(
                            {
                                "templates": _build_templates(
                                    stack, node_cfg, [*item.config, *child.config], blank_templates
                                )
                            }
                            if child.config
                            else {}
                        ),
                        **({"parameters": child.parameters} if child.parameters else {}),
                    }
                    for i, child in enumerate(item.items)
                ]

        retina_manager.parse_configuration(retina_data.test_config)
        retina_manager.push_all_config()


def _build_templates(
    stack: contextlib.ExitStack, node_cfg: _NodeConfig, config_files: list[str], blank_templates: Sequence[str] = ()
) -> Dict:
    main, *extras = node_cfg.templates

    merged = stack.enter_context(tempfile.NamedTemporaryFile(mode="w+"))  # pylint: disable=consider-using-with
    for cfg_file in config_files:
        merged.write(
            (Path(__file__).parent.parent / "configs" / node_cfg.config_folder / cfg_file).read_text(encoding="UTF-8")
        )
        merged.write("\n")
    merged.flush()

    empty_file = stack.enter_context(tempfile.NamedTemporaryFile(mode="w+"))  # pylint: disable=consider-using-with
    empty_file.write(" ")  # Must be non-empty to overwrite default
    empty_file.flush()

    return {
        main: merged.name,
        **{extra: empty_file.name for extra in (*extras, *blank_templates)},
    }
