#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Process parameters / configuration for each client and node type
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jsonschema import validate, ValidationError
from retina.protocol import RanStub

from retina.client.core import storage
from retina.client.core.configuration_port import ConfigurationPort
from retina.client.schemas import schema_path


class ConfigurationService(ConfigurationPort):
    """
    Process parameters / configuration for each client and node type
    """

    # Config file parser
    _CONFIGURATION_SCHEMA_PATH: str = schema_path("configuration_schema.json")
    _TEMPLATES_KEY: str = "templates"
    _MAIN_TEMPLATE_KEY: str = "main"
    _PARAMETERS_KEY: str = "parameters"
    _ITEMS_KEY: str = "node_list"
    _NAME_KEY: str = "name"

    # Push parameters
    _TEMPLATE_PARAM_NAMESPACE: str = "template"

    def __init__(self, *args, **kwargs) -> None:
        self._parameters_from_file: Dict[storage.NodeTypeEnum, Dict[Optional[str], Dict[str, str]]] = {}
        self._parameters_from_cli: Dict[storage.NodeTypeEnum, Dict[Optional[str], Dict[str, str]]] = {}
        self._parameters_calculated: Dict[storage.NodeTypeEnum, Dict[str, Dict[str, str]]] = {}

        self._templates_from_file: Dict[storage.NodeTypeEnum, Dict[Optional[str], Dict[str, str]]] = {}
        self._templates_from_cli: Dict[storage.NodeTypeEnum, Dict[Optional[str], Dict[str, str]]] = {}
        self._templates_calculated: Dict[storage.NodeTypeEnum, Dict[str, Dict[str, str]]] = {}

        with open(
            self._CONFIGURATION_SCHEMA_PATH,
            "r",
            encoding="utf-8",
        ) as file_descriptor:
            self._configuration_schema = json.load(file_descriptor)

        super().__init__(*args, **kwargs)

    def validate_configuration(self, config_file_info: Dict) -> None:
        self._parameters_from_file = {}
        self._parameters_calculated = {}
        self._templates_from_file = {}
        self._templates_calculated = {}

        validate(config_file_info, self._configuration_schema)

        for kind_value, kind_dict in config_file_info.items():
            kind = storage.NodeTypeEnum(kind_value)

            for template_name, template_path in kind_dict.get(self._TEMPLATES_KEY, {}).items():
                self._register_item(
                    kind,
                    None,
                    template_name,
                    self._validate_template(template_path),
                    self._templates_from_file,
                )

            for param_key, param_value in kind_dict.get(self._PARAMETERS_KEY, {}).items():
                self._register_item(kind, None, param_key, param_value, self._parameters_from_file)

            for node in kind_dict.get(self._ITEMS_KEY, ()):
                name = node[self._NAME_KEY]
                if kind in self._parameters_from_file and name in self._parameters_from_file[kind]:
                    self._raise_validation_error(f"Duplicated item name '{name}'")

                for template_name, template_path in node.get(self._TEMPLATES_KEY, {}).items():
                    self._register_item(
                        kind,
                        name,
                        template_name,
                        self._validate_template(template_path),
                        self._templates_from_file,
                    )

                for param_key, param_value in node.get(self._PARAMETERS_KEY, {}).items():
                    self._register_item(kind, name, param_key, param_value, self._parameters_from_file)

        self._validate_name_uniqueness()

    def _validate_template(self, template_path: str) -> str:
        template_path_obj = Path(template_path).resolve()
        try:
            template_path_obj.exists()
        except PermissionError:
            self._raise_validation_error(f"Template file '{template_path_obj}'" " can't be reached: Permission denied.")
        if not template_path_obj.is_file():
            self._raise_validation_error(f"Template file '{template_path_obj}' doesn't exist or is not a file.")
        return str(template_path_obj)

    def _validate_name_uniqueness(self):
        name_array = tuple(
            filter(
                lambda item: item is not None,
                (
                    node_name
                    for node_type_dict in self._parameters_from_file.values()
                    for node_name in node_type_dict.keys()
                ),
            )
        )
        if len(name_array) != len(set(name_array)):
            self._raise_validation_error(f"There are duplicated names in the list item: {name_array}")

    def _raise_validation_error(self, message: str):
        self._parameters_from_file = {}
        self._parameters_calculated = {}
        self._templates_from_file = {}
        self._templates_calculated = {}
        raise ValidationError(message)

    def register_parameter(self, kind: str, name: Optional[str], key: str, value: Any) -> None:
        self._register_item(
            storage.NodeTypeEnum(kind),
            name,
            key,
            value,
            self._parameters_from_cli,
        )

    def register_template(self, kind: str, name: Optional[str], key: str, value: Any) -> None:
        self._register_item(
            storage.NodeTypeEnum(kind),
            name,
            key,
            str(value),
            self._templates_from_cli,
        )

    def reset_all_config(self) -> None:
        self._parameters_from_cli = {}
        self._parameters_from_file = {}
        self._parameters_calculated = {}
        self._templates_from_cli = {}
        self._templates_from_file = {}
        self._templates_calculated = {}

    # pylint:disable=too-many-arguments, too-many-positional-arguments
    def _register_item(
        self,
        kind: storage.NodeTypeEnum,
        name: Optional[str],
        key: str,
        value: str,
        param_dict: Dict,
    ) -> None:
        if name is not None:
            name = name.strip().lower()
        key = key.strip().lower()

        self._parameters_calculated = {}
        self._templates_calculated = {}
        if kind not in param_dict:
            param_dict[kind] = {}
        if name not in param_dict[kind]:
            param_dict[kind][name] = {}
        param_dict[kind][name][key] = value

    def _calculate_parameters(self) -> None:
        # We need to calculate every time because a new client can be created
        # since the last one. Better approach will be to have a callback
        # called when testbed changes

        for node_type, client_list in storage.clients.items():
            self._parameters_calculated[node_type] = {}
            for client in client_list:
                self._parameters_calculated[node_type][client.name] = {}
                self._parameters_calculated[node_type][client.name] = {
                    **self._parameters_from_file.get(node_type, {}).get(None, {}),
                    **self._parameters_from_file.get(node_type, {}).get(client.name, {}),
                    **self._parameters_from_cli.get(node_type, {}).get(None, {}),
                    **self._parameters_from_cli.get(node_type, {}).get(client.name, {}),
                }

        for node_type, client_list in storage.clients.items():
            self._templates_calculated[node_type] = {}
            for client in client_list:
                self._templates_calculated[node_type][client.name] = {}
                self._templates_calculated[node_type][client.name] = {
                    **self._templates_from_file.get(node_type, {}).get(None, {}),
                    **self._templates_from_file.get(node_type, {}).get(client.name, {}),
                    **self._templates_from_cli.get(node_type, {}).get(None, {}),
                    **self._templates_from_cli.get(node_type, {}).get(client.name, {}),
                }

    def push_client_config(self, stub: RanStub) -> None:
        self._calculate_parameters()

        for node_type, client_array in storage.clients.items():
            for client in client_array:
                if client.stub is stub and not client.closed:
                    self._push_item_parameter(client, node_type)
                    return
        raise KeyError("Client was never created or it's already closed")

    def push_all_config(self) -> None:
        self._calculate_parameters()

        for node_type, client_array in storage.clients.items():
            for client in client_array:
                if not client.closed:
                    self._push_item_parameter(client, node_type)

    def _push_item_parameter(self, client: storage.Client, node_type: storage.NodeTypeEnum) -> None:
        for key, value in self._parameters_calculated.get(node_type, {}).get(client.name, {}).items():
            self._com_handler.push_parameter(client.stub, key, yaml.dump(value), node_type.value)

        for key, value in self._templates_calculated.get(node_type, {}).get(client.name, {}).items():
            with open(
                value,
                encoding="utf-8",
            ) as file_descriptor:
                self._com_handler.push_parameter(
                    client.stub,
                    key,
                    file_descriptor.read(),
                    self._TEMPLATE_PARAM_NAMESPACE,
                )
