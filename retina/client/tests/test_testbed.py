#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

import itertools
import unittest
from unittest.mock import MagicMock, call
from jsonschema import ValidationError
from retina.client.core.testbed_service import TestbedService

from retina.client.core.communication_port import CommunicationPort

VALID_UE = {
    "name": "amarisoft-ue",
    "type": "ue",
    "address": "localhost",
    "port": 50061,
}
VALID_UE_2 = {
    "name": "srsue",
    "type": "ue",
    "address": "172.0.0.2",
    "port": 50068,
}
VALID_UE_3 = {
    "name": "android",
    "type": "ue",
    "address": "193.1.2.1",
    "port": 50072,
}

VALID_GNB = {
    "name": "ocudu-gnb",
    "type": "gnb",
    "address": "localhost",
    "port": 50062,
}
VALID_5GC = {
    "name": "open5gs-5gc",
    "type": "5gc",
    "address": "127.0.0.1",
    "port": 50063,
}


class Testbed(unittest.TestCase):
    def setUp(self):
        self.backend = CommunicationPort()
        self.backend.create_client = MagicMock(
            side_effect=lambda resource_type, *com_args: {
                "type": resource_type,
                "com_args": com_args,
            }
        )
        self.backend.close_client = MagicMock()
        self.testbed_use_case = TestbedService(com_handler=self.backend)

    def tearDown(self) -> None:
        self.testbed_use_case.close_all()


class Validation(Testbed):
    def test_given_empty_testbed_then_should_fail(self):
        self.assertRaises(ValidationError, self.testbed_use_case.validate_testbed, None)

    def test_given_invalid_testbed_format_then_should_fail(self):
        for invalid_value in (None, [], " ", 100):
            with self.subTest(invalid_value=invalid_value):
                self.assertRaises(
                    ValidationError,
                    self.testbed_use_case.validate_testbed,
                    invalid_value,
                )

    def test_given_no_id_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {"node_list": [VALID_UE]},
        )

    def test_given_invalid_id_format_then_should_fail(self):
        for invalid_value in (None, [], "", {}, 100):
            with self.subTest(invalid_value=invalid_value):
                self.assertRaises(
                    ValidationError,
                    self.testbed_use_case.validate_testbed,
                    {"id": invalid_value, "node_list": [VALID_UE]},
                )

    def test_given_invalid_node_list_format_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {"id": "id", "node_list": {}},
        )

    def test_given_empty_node_list_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {"id": "id", "node_list": []},
        )

    def test_given_valid_items_then_should_not_fail(self):
        items = (VALID_UE, VALID_GNB, VALID_5GC)
        for r in range(len(items)):
            for subtest_items in itertools.combinations(items, r + 1):
                with self.subTest(items=subtest_items):
                    self.testbed_use_case.validate_testbed(
                        {"id": "id", "node_list": list(subtest_items)}
                    )

    def test_given_missing_mandatory_field_then_should_fail(self):
        for item in (VALID_UE, VALID_GNB, VALID_5GC):
            for field in ("name", "type", "address", "port"):
                with self.subTest(type=item["type"], field=field):
                    new_item = dict(item)
                    new_item.pop(field)
                    self.assertRaises(
                        ValidationError,
                        self.testbed_use_case.validate_testbed,
                        {"id": "id", "node_list": [new_item]},
                    )

    def test_given_more_fields_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {"id": "id", "node_list": [{**VALID_GNB, "extra": "a"}]},
        )

    def test_given_invalid_name_then_should_fail(self):
        for invalid_name in ("", "a b", {}, 1, [], None):
            with self.subTest(invalid_type=invalid_name):
                self.assertRaises(
                    ValidationError,
                    self.testbed_use_case.validate_testbed,
                    {"id": "id", "node_list": [{**VALID_GNB, "name": invalid_name}]},
                )

    def test_given_invalid_type_then_should_fail(self):
        for invalid_type in ("", "aaa", "invalid", None, 0, {}, []):
            with self.subTest(invalid_type=invalid_type):
                self.assertRaises(
                    ValidationError,
                    self.testbed_use_case.validate_testbed,
                    {"id": "id", "node_list": [{**VALID_GNB, "type": invalid_type}]},
                )

    def test_given_invalid_address_then_should_fail(self):
        for invalid_address in ("", 0, 127.0, None, {}, []):
            with self.subTest(invalid_address=invalid_address):
                self.assertRaises(
                    ValidationError,
                    self.testbed_use_case.validate_testbed,
                    {
                        "id": "id",
                        "node_list": [{**VALID_GNB, "address": invalid_address}],
                    },
                )

    def test_given_float_without_decimal_port_then_should_not_fail(self):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [{**VALID_5GC, "port": 100.0}]}
        )

    def test_given_invalid_port_then_should_fail(self):
        for invalid_port in ("", "45", -1, 7.2, None, {}, []):
            with self.subTest(invalid_port=invalid_port):
                self.assertRaises(
                    ValidationError,
                    self.testbed_use_case.validate_testbed,
                    {"id": "id", "node_list": [{**VALID_GNB, "port": invalid_port}]},
                )


    def test_given_duplicate_items_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {
                "id": "id",
                "node_list": [
                    VALID_UE,
                    VALID_UE,
                ],
            },
        )

    def test_given_duplicate_names_same_type_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {
                "id": "id",
                "node_list": [
                    VALID_UE,
                    {**VALID_UE, "port": 0},
                    VALID_5GC,
                ],
            },
        )

    def test_given_duplicate_names_different_types_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE, "name": "repeated_name"},
                    {**VALID_GNB, "name": "repeated_name"},
                    VALID_5GC,
                ],
            },
        )

    def test_given_duplicate_ip_and_port_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {
                "id": "id",
                "node_list": [
                    {**VALID_UE, "address": "localhost", "port": 4444},
                    {**VALID_GNB, "address": "localhost", "port": 4444},
                    VALID_5GC,
                ],
            },
        )

    def test_given_some_valid_and_some_invalid_items_then_should_fail(self):
        self.assertRaises(
            ValidationError,
            self.testbed_use_case.validate_testbed,
            {
                "id": "id",
                "node_list": [
                    VALID_UE,
                    VALID_GNB,
                    {**VALID_5GC, "type": "invalid"},
                ],
            },
        )


class Get(Testbed):
    def test_given_no_testbed_when_get_an_item_then_should_fail(self):
        self.assertRaises(KeyError, self.testbed_use_case.get_ue)
        self.assertRaises(KeyError, self.testbed_use_case.get_gnb)
        self.assertRaises(KeyError, self.testbed_use_case.get_5gc)

    def test_given_one_ue_when_get_client_for_all_types_then_only_ue_should_not_fail(
        self,
    ):
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": [VALID_UE]})
        self.testbed_use_case.get_ue()
        self.backend.create_client.assert_called_once_with(
            VALID_UE["type"], VALID_UE["address"], VALID_UE["port"]
        )
        self.assertRaises(KeyError, self.testbed_use_case.get_gnb)
        self.assertRaises(KeyError, self.testbed_use_case.get_5gc)

    def test_given_one_gnb_when_get_client_for_all_types_then_only_gnb_should_not_fail(
        self,
    ):
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": [VALID_GNB]})
        self.assertRaises(KeyError, self.testbed_use_case.get_ue)
        self.testbed_use_case.get_gnb()
        self.backend.create_client.assert_called_once_with(
            VALID_GNB["type"], VALID_GNB["address"], VALID_GNB["port"]
        )
        self.assertRaises(KeyError, self.testbed_use_case.get_5gc)

    def test_given_one_5gc_when_get_client_for_all_types_then_only_5gc_should_not_fail(
        self,
    ):
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": [VALID_5GC]})
        self.assertRaises(KeyError, self.testbed_use_case.get_ue)
        self.assertRaises(KeyError, self.testbed_use_case.get_gnb)
        self.testbed_use_case.get_5gc()
        self.backend.create_client.assert_called_once_with(
            VALID_5GC["type"], VALID_5GC["address"], VALID_5GC["port"]
        )

    def test_given_an_item_when_get_it_multiple_times_then_it_is_created_only_once(
        self,
    ):
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": [VALID_5GC]})
        self.testbed_use_case.get_5gc()
        self.testbed_use_case.get_5gc()
        self.testbed_use_case.get_5gc()
        self.backend.create_client.assert_called_once_with(
            VALID_5GC["type"], VALID_5GC["address"], VALID_5GC["port"]
        )

    def test_given_multiple_items_when_get_default_then_it_returns_the_first_one(
        self,
    ):
        for testbed in (
            [VALID_UE],
            [VALID_UE, VALID_UE_2],
            [VALID_UE, VALID_UE_2, VALID_UE_3],
        ):
            with self.subTest(num_items=len(testbed)):
                self.testbed_use_case.validate_testbed(
                    {"id": "id", "node_list": testbed}
                )
                self.backend.create_client.reset_mock()
                self.assertEqual(
                    self.testbed_use_case.get_ue(), self.testbed_use_case.get_ue(0)
                )
                self.backend.create_client.assert_called_once_with(
                    VALID_UE["type"], VALID_UE["address"], VALID_UE["port"]
                )
                self.assertRaises(KeyError, self.testbed_use_case.get_gnb)
                self.assertRaises(KeyError, self.testbed_use_case.get_5gc)

    def test_given_one_resource_per_type_when_get_each_type_then_it_returns_the_correct_one(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        self.testbed_use_case.get_ue()
        self.testbed_use_case.get_gnb()
        self.testbed_use_case.get_5gc()
        self.backend.create_client.assert_has_calls(
            (
                call(VALID_UE["type"], VALID_UE["address"], VALID_UE["port"]),
                call(VALID_GNB["type"], VALID_GNB["address"], VALID_GNB["port"]),
                call(VALID_5GC["type"], VALID_5GC["address"], VALID_5GC["port"]),
            )
        )

    def test_given_multiple_items_same_type_when_get_all_of_them_then_should_not_fail(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_UE_2, VALID_UE_3]}
        )
        self.testbed_use_case.get_ue(0)
        self.testbed_use_case.get_ue(1)
        self.testbed_use_case.get_ue(2)
        self.backend.create_client.assert_has_calls(
            (
                call(VALID_UE["type"], VALID_UE["address"], VALID_UE["port"]),
                call(VALID_UE_2["type"], VALID_UE_2["address"], VALID_UE_2["port"]),
                call(VALID_UE_3["type"], VALID_UE_3["address"], VALID_UE_3["port"]),
            )
        )

    def test_given_multiple_items_same_type_when_get_invalid_index_then_should_fail_and_not_create_any_client(
        self,
    ):
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": [VALID_UE]})
        for index in (-10, -1, 10, 1):
            with self.subTest(index=index):
                self.backend.create_client.reset_mock()
                self.assertRaises(IndexError, self.testbed_use_case.get_ue, index)
                self.backend.create_client.assert_not_called()
        with self.subTest(index=0):
            self.backend.create_client.reset_mock()
            self.testbed_use_case.get_ue(0)
            self.backend.create_client.assert_called_once_with(
                VALID_UE["type"], VALID_UE["address"], VALID_UE["port"]
            )

    def test_given_multiple_items_when_get_the_highest_one_then_should_create_it_and_all_below_it(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_UE_2, VALID_UE_3]}
        )
        self.testbed_use_case.get_ue(2)
        self.backend.create_client.assert_has_calls(
            (
                call(VALID_UE["type"], VALID_UE["address"], VALID_UE["port"]),
                call(VALID_UE_2["type"], VALID_UE_2["address"], VALID_UE_2["port"]),
                call(VALID_UE_3["type"], VALID_UE_3["address"], VALID_UE_3["port"]),
            )
        )


class Close(Testbed):
    def test_given_no_testbed_when_close_all_then_should_not_fail(self):
        self.testbed_use_case.close_all()
        self.backend.close_client.assert_not_called()

    def test_given_multiple_items_not_get_when_close_all_then_should_not_close_any_and_not_fail(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        self.testbed_use_case.close_all()
        self.backend.close_client.assert_not_called()

    def test_given_one_client_when_close_all_then_should_close_it(self):
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": [VALID_UE]})
        client = self.testbed_use_case.get_ue(0)
        self.testbed_use_case.close_all()
        self.backend.close_client.assert_called_once_with(client)

    def test_given_multiple_items_when_close_all_then_should_close_then(self):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        client_ue = self.testbed_use_case.get_ue(0)
        client_gnb = self.testbed_use_case.get_gnb()
        client_5gc = self.testbed_use_case.get_5gc()
        self.testbed_use_case.close_all()
        self.backend.close_client.assert_has_calls(
            (
                call(client_ue),
                call(client_gnb),
                call(client_5gc),
            ),
            any_order=True,
        )

    def test_given_multiple_items_same_type_when_close_all_then_should_close_then(self):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_UE_2, VALID_UE_3]}
        )
        client_ue = self.testbed_use_case.get_ue()
        client_ue_2 = self.testbed_use_case.get_ue(1)
        client_ue_3 = self.testbed_use_case.get_ue(2)
        self.testbed_use_case.close_all()
        self.backend.close_client.assert_has_calls(
            (
                call(client_ue),
                call(client_ue_2),
                call(client_ue_3),
            ),
            any_order=True,
        )

    def test_given_multiple_items_and_some_of_them_not_get_when_close_all_then_should_close_only_get(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        client_gnb = self.testbed_use_case.get_gnb()
        self.testbed_use_case.close_all()
        self.backend.close_client.assert_called_once_with(client_gnb)

    def test_given_valid_client_when_close_it_should_not_fail(self):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        client_gnb = self.testbed_use_case.get_gnb()
        self.testbed_use_case.close_client(client_gnb)
        self.backend.close_client.assert_called_once_with(client_gnb)

    def test_given_invalid_client_when_close_it_then_should_fail(self):
        for invalid_client in (None, ""):
            with self.subTest(invalid_client=invalid_client):
                self.assertRaises(
                    KeyError, self.testbed_use_case.close_client, invalid_client
                )

    def test_given_already_closed_client_when_close_again_then_should_not_try_to_close_and_not_fail(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        client_gnb = self.testbed_use_case.get_gnb()
        self.testbed_use_case.close_client(client_gnb)
        self.testbed_use_case.close_client(client_gnb)
        self.testbed_use_case.close_client(client_gnb)
        self.backend.close_client.assert_called_once_with(client_gnb)

    def test_given_closed_client_when_get_again_then_should_create_it_again(self):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        client_5gc = self.testbed_use_case.get_5gc()
        self.testbed_use_case.close_client(client_5gc)
        client_5gc = self.testbed_use_case.get_5gc()
        self.backend.create_client.assert_has_calls(
            (
                call(VALID_5GC["type"], VALID_5GC["address"], VALID_5GC["port"]),
                call(VALID_5GC["type"], VALID_5GC["address"], VALID_5GC["port"]),
            )
        )

    def test_given_already_closed_client_and_open_clients_when_close_all_then_should_close_only_open(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        client_ue = self.testbed_use_case.get_ue()
        client_gnb = self.testbed_use_case.get_gnb()
        client_5gc = self.testbed_use_case.get_5gc()
        self.testbed_use_case.close_client(client_5gc)
        self.backend.close_client.reset_mock()
        self.testbed_use_case.close_all()
        self.backend.close_client.assert_has_calls(
            (
                call(client_ue),
                call(client_gnb),
            ),
            any_order=True,
        )
        self.assertRaises(
            AssertionError, self.backend.close_client.assert_any_call, client_5gc
        )

    def test_given_testbed_when_validate_another_then_should_close_old_clients_and_get_new_ones(
        self,
    ):
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_GNB, VALID_5GC]}
        )
        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.validate_testbed(
            {"id": "id", "node_list": [VALID_UE, VALID_UE_2, VALID_UE_3]}
        )
        self.backend.close_client.assert_called_once_with(client_ue)


if __name__ == "__main__":
    unittest.main()
