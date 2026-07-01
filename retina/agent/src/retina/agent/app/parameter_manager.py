# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Parameter Management:
Parameters can be classified into:
- default parameters: are written into the code, in separated files.
-- generic ones: stored in a yml file.
-- driver specific: each driver has a file with those values
- runtime parameters: parameters set for an execution: cmd args, set during runtime...

This module provides a set of functions to override those parameters.
"""

import logging
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, get_type_hints

import yaml
from typeguard import check_type


class ParameterNamespace(Enum):
    """
    Supported namespaces in parameter management
    """

    TESTBED = "testbed"
    TEMPLATE = "template"
    UE = "ue"
    GNB = "gnb"
    CU = "cu"
    CU_CP = "cu_cp"
    CU_UP = "cu_up"
    DU = "du"
    FIVEGC = "5gc"
    RIC = "ric"


_param_root_dict: Dict[ParameterNamespace, ModuleType] = {}


def _standardize_name(name: str) -> str:
    return name.lower().replace("-", "_")


def convert_to_parameter_source(module_name: str, namespace: ParameterNamespace):
    """
    Make the specified module settable by this `param_manager`
    under the namespace `namespace`
    """
    _param_root_dict[namespace] = sys.modules[module_name]


def parse_param_file(filename: str) -> None:
    """
    Load parameters from an yml file
    :param filename
    :param runtime
    """

    with (
        Path(__file__)
        .parent.joinpath(filename)
        .open(
            encoding="utf-8",
        ) as file_descriptor
    ):
        for key, value in yaml.load(file_descriptor, yaml.FullLoader).items():
            set_parameter(key, value)


def set_parameter(param_name: str, new_value: Any, auto_convert: bool = False) -> None:
    """
    Override a parameter. If it doesn't already exist, the function will raise KeyError
    If `auto_convert` is enabled, it will try to convert the value (must be a string)
    to the correct type.
    :param param_name
    :param value
    :return None
    """
    param_name = _standardize_name(param_name)

    # Validate [root.]name format
    namespace_and_key_array = tuple(param_name.split("."))
    if len(namespace_and_key_array) == 1:
        namespace_and_key_array = ("", *namespace_and_key_array)
    if len(namespace_and_key_array) != 2:
        raise KeyError(f"Unknown param name {param_name}")

    # Get root module
    namespace_value, key = namespace_and_key_array
    namespace = ParameterNamespace(namespace_value)
    root_module = _param_root_dict[namespace]

    if namespace is not ParameterNamespace.TEMPLATE and auto_convert:
        new_value = yaml.load(new_value, yaml.FullLoader)

    # Validate param exists
    if not hasattr(root_module, key):
        logging.warning("New parameter %s", param_name)
    else:
        root_type_hints = get_type_hints(root_module)
        old_value = getattr(root_module, key)
        if key in root_type_hints:
            type_hint = get_type_hints(root_module)[key]
        else:
            logging.warning("param %s from %s namespace doesn't have a valid type hint", key, namespace_value)
            type_hint = type(old_value)
        check_type(key, new_value, type_hint)
        if old_value == new_value:
            return

    setattr(root_module, key, new_value)
    if isinstance(new_value, str) and len(new_value.splitlines()) > 1:
        new_value = new_value.splitlines()[0] + " ..."
    logging.info("Parameter %s set to %s", param_name, new_value)
