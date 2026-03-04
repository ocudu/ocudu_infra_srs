# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock, call

import yaml
from jsonschema import ValidationError
from retina.client.core.communication_port import CommunicationPort
from retina.client.core.configuration_service import ConfigurationService
from retina.client.core.testbed_service import TestbedService

from .test_testbed import VALID_5GC, VALID_GNB, VALID_UE, VALID_UE_2, VALID_UE_3


PARAMETERS_DICT = {"ip": "172.18.0.2", "port": 6000}
PARAMETERS_DICT_OVERRIDE_1 = {"port": 0}
PARAMETERS_DICT_OVERRIDE_2 = {"port": -100}
PARAMETERS_DICT_OVERRIDE_3 = {"port": 100}
PARAMETERS_DICT_ALT_2 = {"hw_type": "sdr", "model": "b300"}
PARAMETERS_DICT_ALT_3 = {"version": 0.1}
PARAMETERS_DICT_ALT_4 = {"extra": False}

TEMPLATE_PARAM_SPACE = "template"


class ConfigurationTestCase(unittest.TestCase):
    MULTIPLE_TRIES = 30

    @staticmethod
    def get_push_parameter_calls(client, param_dict, is_template=False):
        return tuple(
            call(
                client,
                key,
                str(value) if is_template else yaml.dump(value),
                TEMPLATE_PARAM_SPACE if is_template else client["type"],
            )
            for key, value in param_dict.items()
        )

    def assertPushedParametersExactCalls(self, calls):
        self.backend.push_parameter.assert_has_calls(
            calls,
            any_order=True,
        )
        self.assertEqual(self.backend.push_parameter.call_count, len(calls))

    def setUp(self):
        self.backend = CommunicationPort()
        self.backend.create_client = MagicMock(
            side_effect=lambda resource_type, *com_args: {
                "type": resource_type,
                "com_args": com_args,
            }
        )
        self.backend.close_client = MagicMock()
        self.backend.push_parameter = MagicMock()
        self.testbed_use_case = TestbedService(com_handler=self.backend)
        self.configuration_use_case = ConfigurationService(com_handler=self.backend)

    def tearDown(self) -> None:
        self.testbed_use_case.close_all()


class ValidationBasicErrors(ConfigurationTestCase):
    def test_given_empty_conf_file_then_should_not_fail(self):
        self.assertRaises(ValidationError, self.configuration_use_case.validate_configuration, None)

    def test_given_invalid_conf_format_then_should_fail(self):
        for conf in ([], ""):
            with self.subTest(conf=conf):
                self.assertRaises(
                    ValidationError,
                    self.configuration_use_case.validate_configuration,
                    conf,
                )

    def test_given_invalid_type_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.configuration_use_case.validate_configuration,
            {"invalid": {}},
        )

    def test_given_invalid_type_format_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.configuration_use_case.validate_configuration,
            {"ue": []},
        )

    def test_given_invalid_type_property_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.configuration_use_case.validate_configuration,
            {"ue": {"invalid": 1}},
        )

    def test_given_invalid_type_items_format_then_should_fail(self):
        for invalid_value in ("", 1, {}, None):
            with self.subTest(invalid_value=invalid_value):
                self.assertRaises(
                    ValidationError,
                    self.configuration_use_case.validate_configuration,
                    {"ue": {"node_list": invalid_value}},
                )

    def test_given_invalid_type_parameters_format_then_should_fail(self):
        for invalid_value in ("", 1, [], None):
            with self.subTest(invalid_value=invalid_value):
                self.assertRaises(
                    ValidationError,
                    self.configuration_use_case.validate_configuration,
                    {"ue": {"parameters": invalid_value}},
                )

    def test_given_invalid_type_templates_format_then_should_fail(self):
        for invalid_value in (
            "",
            __file__,
            1,
            [],
            None,
            {"main": 17},
            {"main": Path.cwd().joinpath("_no_exist:.txt")},  # Non existing file
            {"main": str(Path.cwd())},  # Folder
            {"main": "/root/file.txt"},  # Permission Denied or Not found
            {"main": "C://System32"},  # Permission Denied not found
        ):
            with self.subTest(invalid_value=invalid_value):
                self.assertRaises(
                    ValidationError,
                    self.configuration_use_case.validate_configuration,
                    {"ue": {"templates": invalid_value}},
                )


class ValidationItemErrors(ConfigurationTestCase):
    def test_given_item_without_name_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.configuration_use_case.validate_configuration,
            {"ue": {"node_list": [{"parameters": {}}]}},
        )

    def test_given_invalid_item_name_format_then_should_fail(self):
        for invalid_value in ("", "a b", {}, 1, [], None):
            with self.subTest(invalid_value=invalid_value):
                self.assertRaises(
                    ValidationError,
                    self.configuration_use_case.validate_configuration,
                    {"ue": {"node_list": [{"name": invalid_value}]}},
                )

    def test_given_invalid_item_property_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.configuration_use_case.validate_configuration,
            {"ue": {"node_list": [{"name": "valid", "invalid": 1}]}},
        )

    def test_given_invalid_item_parameters_format_then_should_fail(self):
        for invalid_value in ("", 1, [], None):
            with self.subTest(invalid_value=invalid_value):
                self.assertRaises(
                    ValidationError,
                    self.configuration_use_case.validate_configuration,
                    {"ue": {"node_list": [{"name": "valid", "parameters": invalid_value}]}},
                )

    def test_given_invalid_item_template_format_then_should_fail(self):
        for invalid_value in (
            "",
            __file__,
            1,
            [],
            None,
            {"main": 17},
            {"main": Path.cwd().joinpath("_no_exist:.txt")},  # Non existing file
            {"main": str(Path.cwd())},  # Folder
            {"main": "/root/file.txt"},  # Permission Denied or Not found
            {"main": "C://System32"},  # Permission Denied not found
        ):
            with self.subTest(invalid_value=invalid_value):
                self.assertRaises(
                    ValidationError,
                    self.configuration_use_case.validate_configuration,
                    {"ue": {"node_list": [{"name": "valid", "templates": invalid_value}]}},
                )

    def test_given_duplicated_items_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.configuration_use_case.validate_configuration,
            {
                "ue": {
                    "node_list": [
                        {"name": "a"},
                        {"name": "a"},
                    ]
                }
            },
        )

    def test_given_duplicated_item_name_same_type_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.configuration_use_case.validate_configuration,
            {
                "ue": {
                    "node_list": [
                        {"name": "a", "parameters": PARAMETERS_DICT},
                        {"name": "a", "parameters": {}},
                    ]
                }
            },
        )

    def test_given_duplicated_item_name_same_type_and_only_one_with_params_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {"name": "a"},
                        {"name": "a", "parameters": {}},
                    ]
                }
            },
        )

    def test_given_no_name_then_should_not_fail(self):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {"parameters": {}},
                "gnb": {"parameters": PARAMETERS_DICT},
                "5gc": {"parameters": PARAMETERS_DICT_ALT_2},
            }
        )

    def test_given_duplicated_item_name_different_type_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.configuration_use_case.validate_configuration,
            {
                "ue": {
                    "node_list": [
                        {"name": "a", "parameters": PARAMETERS_DICT},
                    ]
                },
                "gnb": {
                    "node_list": [
                        {"name": "a", "parameters": {"key": "value"}},
                    ]
                },
            },
        )

    def test_given_duplicated_item_name_different_type_only_one_with_param_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {"name": "a"},
                    ]
                },
                "gnb": {
                    "node_list": [
                        {"name": "a", "parameters": {"key": "value"}},
                    ]
                },
            },
        )


class PushParameterConfigAndCli(ConfigurationTestCase):
    def setUp(self):
        super().setUp()
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_UE_2},
                    {**VALID_UE_3},
                    {**VALID_GNB},
                    {**VALID_5GC},
                ],
            }
        )

    def test_given_cfile_type_parameter_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration({"ue": {"parameters": PARAMETERS_DICT}})
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()

        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            )
        )

    def test_given_cfile_item_parameter_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {"ue": {"node_list": [{"name": VALID_UE["name"], "parameters": PARAMETERS_DICT}]}}
        )
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
        )

    def test_given_cli_type_parameter_when_push_parameters_then_should_not_fail(
        self,
    ):
        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)

        self.configuration_use_case.validate_configuration({})
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            )
        )

    def test_given_cli_item_parameter_when_push_parameters_then_should_not_fail(
        self,
    ):
        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        self.configuration_use_case.validate_configuration({})
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
        )

    def test_given_cfile_type_param_and_another_cfile_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [{"name": VALID_UE["name"], "parameters": PARAMETERS_DICT_ALT_2}],
                }
            }
        )
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cfile_type_param_and_same_cfile_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_OVERRIDE_1,
                        }
                    ],
                }
            }
        )
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cli_type_param_and_another_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)

        for key, value in PARAMETERS_DICT_ALT_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cli_type_param_and_same_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)

        for key, value in PARAMETERS_DICT_OVERRIDE_1.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cfile_type_param_and_another_cli_type_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                }
            }
        )
        for key, value in PARAMETERS_DICT_ALT_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT_ALT_2),
            ),
        )

    def test_given_cfile_type_param_and_same_cli_type_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                }
            }
        )
        for key, value in PARAMETERS_DICT_OVERRIDE_1.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
                *self.get_push_parameter_calls(client_ue_1, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
                *self.get_push_parameter_calls(client_ue_2, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
            ),
        )

    def test_given_cfile_type_param_and_another_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                }
            }
        )
        for key, value in PARAMETERS_DICT_ALT_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cfile_type_param_and_same_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                }
            }
        )
        for key, value in PARAMETERS_DICT_OVERRIDE_1.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cli_type_param_and_another_cfile_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_ALT_2,
                        }
                    ],
                }
            }
        )
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cli_type_param_and_same_cfile_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_OVERRIDE_1,
                        }
                    ],
                }
            }
        )
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cfile_item_param_and_another_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_ALT_2,
                        }
                    ],
                }
            }
        )
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
            ),
        )

    def test_given_cfile_item_param_and_same_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        for key, value in PARAMETERS_DICT_OVERRIDE_1.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT,
                        }
                    ],
                }
            }
        )
        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
        )

    def test_given_cfile_type_param_and_another_cli_type_param_and_cfile_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_ALT_2,
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_ALT_3.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_3),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT_ALT_3),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT_ALT_3),
            ),
        )

    def test_given_cfile_type_param_and_same_cli_type_param_and_cfile_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_OVERRIDE_1,
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_OVERRIDE_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_2}),
                *self.get_push_parameter_calls(client_ue_1, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_2}),
                *self.get_push_parameter_calls(client_ue_2, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_2}),
            ),
        )

    def test_given_cfile_type_param_and_another_cli_item_param_and_cfile_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_ALT_2,
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_ALT_3.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_3),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cfile_type_param_and_same_cli_item_param_and_cfile_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_OVERRIDE_1,
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_OVERRIDE_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_2}),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cfile_type_param_and_another_cli_type_param_and_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_ALT_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)
        for key, value in PARAMETERS_DICT_ALT_3.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_3),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT_ALT_2),
            ),
        )

    def test_given_cfile_type_param_and_same_cli_type_param_and_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_OVERRIDE_1.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)
        for key, value in PARAMETERS_DICT_OVERRIDE_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_2}),
                *self.get_push_parameter_calls(client_ue_1, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
                *self.get_push_parameter_calls(client_ue_2, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_1}),
            ),
        )

    def test_given_cfile_item_param_and_another_cli_type_param_and_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT,
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_ALT_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)
        for key, value in PARAMETERS_DICT_ALT_3.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_3),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT_ALT_2),
            ),
        )

    def test_given_cfile_item_param_and_same_cli_type_param_and_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_OVERRIDE_1,
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)
        for key, value in PARAMETERS_DICT_OVERRIDE_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_2}),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
            ),
        )

    def test_given_cfile_type_param_and_another_cfile_item_param_and_cli_type_param_and_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_ALT_2,
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_ALT_3.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)
        for key, value in PARAMETERS_DICT_ALT_4.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_2),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_3),
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT_ALT_4),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_1, PARAMETERS_DICT_ALT_3),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_ue_2, PARAMETERS_DICT_ALT_3),
            ),
        )

    def test_given_cfile_type_param_and_same_cfile_item_param_and_cli_type_param_and_cli_item_param_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "parameters": PARAMETERS_DICT,
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "parameters": PARAMETERS_DICT_OVERRIDE_1,
                        }
                    ],
                }
            }
        )
        for key, value in PARAMETERS_DICT_OVERRIDE_2.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], None, key, value)
        for key, value in PARAMETERS_DICT_OVERRIDE_3.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_ue_2 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_3}),
                *self.get_push_parameter_calls(client_ue_1, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_2}),
                *self.get_push_parameter_calls(client_ue_2, {**PARAMETERS_DICT, **PARAMETERS_DICT_OVERRIDE_2}),
            ),
        )


class PushParametersNonExistent(ConfigurationTestCase):
    def setUp(self):
        super().setUp()
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_UE_2},
                    {**VALID_UE_3},
                    {**VALID_GNB},
                    {**VALID_5GC},
                ],
            }
        )

    def test_given_conf_file_with_non_existent_item_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {"parameters": PARAMETERS_DICT},
                "gnb": {"node_list": [{"name": "non_existing_name", "parameters": PARAMETERS_DICT}]},
            }
        )
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.backend.push_parameter.assert_not_called()

    def test_given_cli_non_existent_type_then_should_fail(self):
        self.assertRaises(
            ValueError,
            self.configuration_use_case.register_parameter,
            "fake_type",
            None,
            "key",
            "value",
        )

    def test_given_cli_non_existent_item_when_push_parameters_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.register_parameter(
            VALID_UE["type"],
            None,
            "key",
            "value",
        )
        self.configuration_use_case.register_parameter(
            VALID_GNB["type"],
            "fake_name",
            "key",
            "value",
        )
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.backend.push_parameter.assert_not_called()

    def test_given_config_when_get_one_client_at_time_then_should_not_fail(self):
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_GNB},
                    {**VALID_5GC},
                ],
            }
        )

        self.configuration_use_case.validate_configuration(
            {
                "ue": {"parameters": PARAMETERS_DICT},
                "gnb": {"parameters": PARAMETERS_DICT_ALT_2},
                "5gc": {"parameters": PARAMETERS_DICT_ALT_3},
            }
        )

        ue = self.testbed_use_case.get_ue()
        self.configuration_use_case.push_client_config(ue)
        self.assertPushedParametersExactCalls(self.get_push_parameter_calls(ue, PARAMETERS_DICT))

        self.backend.push_parameter.reset_mock()
        gnb = self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(gnb)
        self.assertPushedParametersExactCalls(self.get_push_parameter_calls(gnb, PARAMETERS_DICT_ALT_2))

        self.backend.push_parameter.reset_mock()
        fivegc = self.testbed_use_case.get_5gc()
        self.configuration_use_case.push_client_config(fivegc)
        self.assertPushedParametersExactCalls(self.get_push_parameter_calls(fivegc, PARAMETERS_DICT_ALT_3))


class ResetParameters(ConfigurationTestCase):
    def test_given_no_conf_when_reset_parameters_then_should_not_fail(self):
        self.configuration_use_case.reset_all_config()
        self.configuration_use_case.reset_all_config()

    def test_given_conf_param_when_reset_parameters_then_should_not_push(self):
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_UE_2},
                    {**VALID_5GC},
                ],
            }
        )
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [{"name": VALID_UE["name"], "parameters": PARAMETERS_DICT}],
                },
                "gnb": {"parameters": PARAMETERS_DICT_ALT_2},
                "5gc": {"parameters": PARAMETERS_DICT_ALT_3},
            }
        )
        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_5gc = self.testbed_use_case.get_5gc(0)
        self.configuration_use_case.push_all_config()
        client_ue_0 = self.testbed_use_case.get_ue(0)
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_5gc, PARAMETERS_DICT_ALT_3),
            )
        )

        self.backend.push_parameter.reset_mock()
        self.configuration_use_case.reset_all_config()
        self.configuration_use_case.push_all_config()
        self.backend.push_parameter.assert_not_called()

        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [{"name": VALID_UE["name"], "parameters": PARAMETERS_DICT}],
                },
            }
        )
        client_ue_0 = self.testbed_use_case.get_ue(0)
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
        )

    def test_given_cli_param_when_reset_parameters_then_should_not_push(self):
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_UE_2},
                    {**VALID_5GC},
                ],
            }
        )

        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)
        for key, value in PARAMETERS_DICT_ALT_2.items():
            self.configuration_use_case.register_parameter(VALID_GNB["type"], None, key, value)
        for key, value in PARAMETERS_DICT_ALT_3.items():
            self.configuration_use_case.register_parameter(VALID_5GC["type"], None, key, value)

        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_5gc = self.testbed_use_case.get_5gc(0)
        self.configuration_use_case.push_all_config()
        client_ue_0 = self.testbed_use_case.get_ue(0)
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_5gc, PARAMETERS_DICT_ALT_3),
            )
        )

        self.backend.push_parameter.reset_mock()
        self.configuration_use_case.reset_all_config()
        self.configuration_use_case.push_all_config()
        self.backend.push_parameter.assert_not_called()

        for key, value in PARAMETERS_DICT.items():
            self.configuration_use_case.register_parameter(VALID_UE["type"], VALID_UE["name"], key, value)

        client_ue_0 = self.testbed_use_case.get_ue(0)
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
        )

    def test_given_config_and_cli_param_when_reset_parameters_then_should_not_push(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_UE_2},
                    {**VALID_5GC},
                ],
            }
        )

        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [{"name": VALID_UE["name"], "parameters": PARAMETERS_DICT}],
                },
            }
        )
        for key, value in PARAMETERS_DICT_ALT_2.items():
            self.configuration_use_case.register_parameter(VALID_GNB["type"], None, key, value)
        for key, value in PARAMETERS_DICT_ALT_3.items():
            self.configuration_use_case.register_parameter(VALID_5GC["type"], None, key, value)

        client_ue_1 = self.testbed_use_case.get_ue(1)
        client_5gc = self.testbed_use_case.get_5gc(0)
        self.configuration_use_case.push_all_config()
        client_ue_0 = self.testbed_use_case.get_ue(0)
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(client_ue_0, PARAMETERS_DICT),
                *self.get_push_parameter_calls(client_5gc, PARAMETERS_DICT_ALT_3),
            )
        )

        self.backend.push_parameter.reset_mock()
        self.configuration_use_case.reset_all_config()
        self.configuration_use_case.push_all_config()
        self.backend.push_parameter.assert_not_called()

    def test_given_a_testbed_with_config_when_reset_parameters_and_new_testbed_with_new_config_then_should_push_new_params(
        self,
    ):
        # First testbed
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": [{**VALID_UE}]})
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [{"name": VALID_UE["name"], "parameters": PARAMETERS_DICT}],
                },
            }
        )
        ue = self.testbed_use_case.get_ue()
        self.configuration_use_case.push_client_config(ue)
        self.assertPushedParametersExactCalls(self.get_push_parameter_calls(ue, PARAMETERS_DICT))
        self.backend.push_parameter.reset_mock()

        # Second one
        self.configuration_use_case.reset_all_config()
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": [{**VALID_GNB}]})
        self.configuration_use_case.validate_configuration(
            {
                "gnb": {"parameters": PARAMETERS_DICT_ALT_2},
            }
        )

        gnb = self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(self.get_push_parameter_calls(gnb, PARAMETERS_DICT_ALT_2))


class PushTemplateBase(ConfigurationTestCase):
    TEMPLATE_CONTENT_ARRAY = [
        """
        multi
        line
        """,
        "a as da sd asd",
        """ 
        
        
        asdasd
        """,
        "empty",
    ]

    def setUp(self):
        super().setUp()
        self.temp_file_array = [self._create_and_fill_temp_file(content) for content in self.TEMPLATE_CONTENT_ARRAY]
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_UE_2},
                    {**VALID_UE_3},
                    {**VALID_GNB},
                    {**VALID_5GC},
                ],
            }
        )

    def _create_and_fill_temp_file(self, content):
        temp_file = NamedTemporaryFile(mode="w+", delete=False)
        temp_file.write(content)
        temp_file.flush()
        temp_file.close()
        return Path(temp_file.name).resolve()

    def tearDown(self) -> None:
        super().tearDown()
        for file in self.temp_file_array:
            file.unlink()


class PushTemplateConfigFile(PushTemplateBase):
    def test_given_cfile_type_template_when_push_client_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue, {"main": self.TEMPLATE_CONTENT_ARRAY[0]}, is_template=True),
        )

    def test_given_cfile_type_template_when_push_all_config_then_should_not_fail(self):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
            ),
        )

    def test_given_cfile_item_template_when_push_client_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "templates": {"main": str(self.temp_file_array[0])},
                        }
                    ],
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue, {"main": self.TEMPLATE_CONTENT_ARRAY[0]}, is_template=True),
        )

    def test_given_cfile_item_template_when_push_all_config_then_should_not_fail(self):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "templates": {"main": str(self.temp_file_array[0])},
                        }
                    ],
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue, {"main": self.TEMPLATE_CONTENT_ARRAY[0]}, is_template=True),
        )

    def test_given_cfile_type_template_and_another_cfile_item_template_when_push_client_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "templates": {"secondary": str(self.temp_file_array[1])},
                        }
                    ],
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue,
                    {"secondary": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
            )
        )

    def test_given_cfile_type_template_and_another_cfile_item_template_when_push_all_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "templates": {"secondary": str(self.temp_file_array[1])},
                        }
                    ],
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue,
                    {"secondary": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
            )
        )

    def test_given_cfile_type_template_and_same_cfile_item_template_when_push_client_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "templates": {"main": str(self.temp_file_array[1])},
                        }
                    ],
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(
                client_ue,
                {"main": self.TEMPLATE_CONTENT_ARRAY[1]},
                is_template=True,
            ),
        )

    def test_given_cfile_type_template_and_same_cfile_item_template_when_push_all_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "templates": {"main": str(self.temp_file_array[1])},
                        }
                    ],
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
            )
        )

    def test_given_template_when_get_one_client_at_time_then_should_not_fail(self):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {"templates": {"main": str(self.temp_file_array[0])}},
                "gnb": {"templates": {"main": str(self.temp_file_array[1])}},
                "5gc": {"templates": {"main": str(self.temp_file_array[2])}},
            }
        )

        ue = self.testbed_use_case.get_ue()
        self.configuration_use_case.push_client_config(ue)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(ue, {"main": self.TEMPLATE_CONTENT_ARRAY[0]}, is_template=True)
        )

        self.backend.push_parameter.reset_mock()
        gnb = self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(gnb)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(gnb, {"main": self.TEMPLATE_CONTENT_ARRAY[1]}, is_template=True)
        )

        self.backend.push_parameter.reset_mock()
        fivegc = self.testbed_use_case.get_5gc()
        self.configuration_use_case.push_client_config(fivegc)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(fivegc, {"main": self.TEMPLATE_CONTENT_ARRAY[2]}, is_template=True)
        )


class PushTemplateCli(PushTemplateBase):
    def test_given_cli_type_template_when_push_client_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.register_template(VALID_UE["type"], None, "main", str(self.temp_file_array[0]))
        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue, {"main": self.TEMPLATE_CONTENT_ARRAY[0]}, is_template=True),
        )

    def test_given_cli_type_template_when_push_all_config_then_should_not_fail(self):
        self.configuration_use_case.register_template(VALID_UE["type"], None, "main", str(self.temp_file_array[0]))
        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
            ),
        )

    def test_given_cli_item_template_when_push_client_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.register_template(
            VALID_UE["type"], VALID_UE["name"], "main", str(self.temp_file_array[0])
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue, {"main": self.TEMPLATE_CONTENT_ARRAY[0]}, is_template=True),
        )

    def test_given_cli_item_template_when_push_all_config_then_should_not_fail(self):
        self.configuration_use_case.register_template(
            VALID_UE["type"], VALID_UE["name"], "main", str(self.temp_file_array[0])
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(client_ue, {"main": self.TEMPLATE_CONTENT_ARRAY[0]}, is_template=True),
        )

    def test_given_cli_type_template_and_another_cli_item_template_when_push_client_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.register_template(VALID_UE["type"], None, "main", str(self.temp_file_array[0]))
        self.configuration_use_case.register_template(
            VALID_UE["type"],
            VALID_UE["name"],
            "secondary",
            str(self.temp_file_array[1]),
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue,
                    {"secondary": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
            )
        )

    def test_given_cli_type_template_and_another_cli_item_template_when_push_all_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.register_template(VALID_UE["type"], None, "main", str(self.temp_file_array[0]))
        self.configuration_use_case.register_template(
            VALID_UE["type"],
            VALID_UE["name"],
            "secondary",
            str(self.temp_file_array[1]),
        )

        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue,
                    {"secondary": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
            )
        )

    def test_given_cli_type_template_and_same_cli_item_template_when_push_client_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.register_template(VALID_UE["type"], None, "main", str(self.temp_file_array[0]))
        self.configuration_use_case.register_template(
            VALID_UE["type"], VALID_UE["name"], "main", str(self.temp_file_array[1])
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            self.get_push_parameter_calls(
                client_ue,
                {"main": self.TEMPLATE_CONTENT_ARRAY[1]},
                is_template=True,
            ),
        )

    def test_given_cli_type_template_and_same_cli_item_template_when_push_all_config_then_should_not_fail(
        self,
    ):
        self.configuration_use_case.register_template(VALID_UE["type"], None, "main", str(self.temp_file_array[0]))
        self.configuration_use_case.register_template(
            VALID_UE["type"], VALID_UE["name"], "main", str(self.temp_file_array[1])
        )

        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
            )
        )


class PushTemplateConfigFileAndCli(PushTemplateBase):
    def test_given_multiple_templates_by_type_and_item_both_cfile_and_cli_when_push_parameters_then_should_push_all(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "templates": {"second": str(self.temp_file_array[1])},
                        }
                    ],
                },
            }
        )

        self.configuration_use_case.register_template(VALID_UE["type"], None, "third", str(self.temp_file_array[2]))
        self.configuration_use_case.register_template(
            VALID_UE["type"],
            VALID_UE["name"],
            "fourth",
            str(self.temp_file_array[3]),
        )

        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue,
                    {"second": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue,
                    {"third": self.TEMPLATE_CONTENT_ARRAY[2]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue,
                    {"fourth": self.TEMPLATE_CONTENT_ARRAY[3]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"third": self.TEMPLATE_CONTENT_ARRAY[2]},
                    is_template=True,
                ),
            )
        )

    def test_given_cfile_type_template_and_cli_type_template_when_push_parameters_then_push_overridden_value(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                }
            }
        )

        self.configuration_use_case.register_template(VALID_UE["type"], None, "main", str(self.temp_file_array[1]))

        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[1]},
                    is_template=True,
                ),
            )
        )

    def test_given_same_templates_by_type_and_item_both_cfile_and_cli_when_push_parameters_then_should_push_overridden_value(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                    "node_list": [
                        {
                            "name": VALID_UE["name"],
                            "templates": {"main": str(self.temp_file_array[1])},
                        }
                    ],
                },
            }
        )

        self.configuration_use_case.register_template(VALID_UE["type"], None, "main", str(self.temp_file_array[2]))
        self.configuration_use_case.register_template(
            VALID_UE["type"],
            VALID_UE["name"],
            "main",
            str(self.temp_file_array[3]),
        )

        client_ue = self.testbed_use_case.get_ue()
        client_ue_1 = self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[3]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue_1,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[2]},
                    is_template=True,
                ),
            )
        )


class PushTemplateNoConflict(PushTemplateBase):
    def test_given_template_and_param_called_template_then_there_are_no_conflicts(
        self,
    ):
        self.configuration_use_case.validate_configuration(
            {
                "ue": {
                    "templates": {"main": str(self.temp_file_array[0])},
                    "parameters": {"templates": str(self.temp_file_array[0])},
                },
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_gnb()
        self.configuration_use_case.push_client_config(client_ue)
        self.assertPushedParametersExactCalls(
            (
                *self.get_push_parameter_calls(
                    client_ue,
                    {"main": self.TEMPLATE_CONTENT_ARRAY[0]},
                    is_template=True,
                ),
                *self.get_push_parameter_calls(
                    client_ue,
                    {"templates": str(self.temp_file_array[0])},
                ),
            )
        )


class ClosedClientsPushParameters(ConfigurationTestCase):
    def test_given_invalid_client_when_push_client_config_then_should_fail(self):
        for invalid_client in (None, ""):
            with self.subTest(invalid_client=invalid_client):
                self.assertRaises(
                    KeyError,
                    self.configuration_use_case.push_client_config,
                    invalid_client,
                )
                self.backend.push_parameter.assert_not_called()

    def test_given_closed_client_when_push_client_config_then_should_fail(self):
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_UE_2},
                    {**VALID_5GC},
                ],
            }
        )
        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.close_client(client_ue)
        self.assertRaises(
            KeyError,
            self.configuration_use_case.push_client_config,
            client_ue,
        )
        self.backend.push_parameter.assert_not_called()

    def test_given_some_closed_clients_and_some_open_when_push_all_config_then_should_skip_the_closed_ones(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE},
                    {**VALID_UE_2},
                    {**VALID_GNB},
                ],
            }
        )
        self.configuration_use_case.validate_configuration(
            {
                "ue": {"parameters": PARAMETERS_DICT_ALT_3},
                "gnb": {"parameters": PARAMETERS_DICT},
            }
        )

        client_ue = self.testbed_use_case.get_ue()
        client_gnb = self.testbed_use_case.get_gnb()
        self.testbed_use_case.close_client(client_ue)
        self.configuration_use_case.push_all_config()
        self.assertPushedParametersExactCalls(self.get_push_parameter_calls(client_gnb, PARAMETERS_DICT))


if __name__ == "__main__":
    unittest.main()
