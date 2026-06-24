# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Parse and process testbed inputs
"""

import json
import logging
import typing
from collections import OrderedDict
from typing import Dict

from jsonschema import validate, ValidationError
from retina.protocol import RanStub
from retina.protocol.channel_emulator_pb2_grpc import ChannelEmulatorStub
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import CUStub, DUStub, GNBStub
from retina.protocol.ric_pb2_grpc import NearRtRicStub
from retina.protocol.ue_pb2_grpc import UEStub

from retina.client.core import storage
from retina.client.core.storage import Client, NodeTypeEnum
from retina.client.core.testbed_port import NodeInfo, TestbedPort
from retina.client.schemas import schema_path


class TestbedService(TestbedPort):
    """
    Parse and process testbed inputs
    """

    _TESTBED_SCHEMA_PATH: str = schema_path("testbed_schema.json")
    _ITEMS_KEY: str = "node_list"
    _KIND_KEY: str = "type"
    _NAME_KEY: str = "name"
    _IP_KEY: str = "address"
    _PORT_KEY: str = "port"
    _RESOURCES_KEY: str = "resources"

    def __init__(self, *args, **kwargs) -> None:
        self._testbed_info: Dict[str, typing.OrderedDict[str, NodeInfo]] = {}
        storage.clients.clear()

        with open(
            self._TESTBED_SCHEMA_PATH,
            "r",
            encoding="utf-8",
        ) as file_descriptor:
            self._testbed_schema = json.load(file_descriptor)

        super().__init__(*args, **kwargs)

    def validate_testbed(self, testbed: Dict) -> None:
        self.close_all()
        storage.clients.clear()
        self._testbed_info = {}

        validate(testbed, self._testbed_schema)

        for item in testbed.get(self._ITEMS_KEY, ()):
            kind = item[self._KIND_KEY]
            if kind not in self._testbed_info:
                self._testbed_info[kind] = OrderedDict()
            name = item[self._NAME_KEY]
            if name in self._testbed_info[kind]:
                # Name already used in same node from the same type
                self._raise_validation_error(f"Name '{name}' duplicated in type '{kind}'")
            self._testbed_info[kind][name] = NodeInfo(
                address=item[self._IP_KEY],
                port=item[self._PORT_KEY],
                resources=item.get(self._RESOURCES_KEY, []),
            )

        self._validate_name_uniqueness()
        self._validate_ip_port_uniqueness()

    def _validate_name_uniqueness(self):
        name_array = tuple(
            node_name for node_type_dict in self._testbed_info.values() for node_name in node_type_dict.keys()
        )
        if len(name_array) != len(set(name_array)):
            self._raise_validation_error(f"There are duplicated names in the list item: {name_array}")

    def _validate_ip_port_uniqueness(self):
        ip_port_array = tuple(
            (node.address, node.port)
            for node_type_dict in self._testbed_info.values()
            for node in node_type_dict.values()
        )
        if len(ip_port_array) != len(set(ip_port_array)):
            self._raise_validation_error(f"There are duplicated ip+port values in the list item: {ip_port_array}")

    def _raise_validation_error(self, message: str):
        self._testbed_info = {}
        raise ValidationError(message)

    def get_testbed_info(self) -> Dict[str, typing.OrderedDict[str, NodeInfo]]:
        return self._testbed_info

    def get_ue(self, index: int = 0) -> UEStub:
        return self._get_item(NodeTypeEnum.UE, index)

    def get_gnb(self, index: int = 0) -> GNBStub:
        return self._get_item(NodeTypeEnum.GNB, index)

    def get_cu(self, index: int = 0) -> CUStub:
        return self._get_item(NodeTypeEnum.CU, index)

    def get_cu_cp(self, index: int = 0) -> CUStub:
        return self._get_item(NodeTypeEnum.CU_CP, index)

    def get_cu_up(self, index: int = 0) -> CUStub:
        return self._get_item(NodeTypeEnum.CU_UP, index)

    def get_du(self, index: int = 0) -> DUStub:
        return self._get_item(NodeTypeEnum.DU, index)

    def get_5gc(self, index: int = 0) -> FiveGCStub:
        return self._get_item(NodeTypeEnum.FIVEGC, index)

    def get_ric(self, index: int = 0) -> NearRtRicStub:
        return self._get_item(NodeTypeEnum.RIC, index)

    def get_channel_emulator(self, index: int = 0) -> ChannelEmulatorStub:
        return self._get_item(NodeTypeEnum.CHANNEL_EMULATOR, index)

    def _get_item(self, stub_type: NodeTypeEnum, index: int = 0) -> RanStub:
        if stub_type.value not in self._testbed_info:
            raise KeyError(
                f"No nodes of type `{stub_type.value}`. "
                + f"Available node types are {tuple(self._testbed_info.keys())}."
            )

        if index < 0:
            raise IndexError("Negative index not allowed here.")

        num_items_of_type = len(self._testbed_info[stub_type.value])
        if num_items_of_type == 0 or index >= num_items_of_type:
            raise IndexError(
                f"Requested index {index} while "
                f"there are only {num_items_of_type} items "
                f"of type '{stub_type.value}'"
            )

        if stub_type not in storage.clients:
            storage.clients[stub_type] = []

        # Need to review all clients for this type until the specified index
        # Create them if not exist, or reopen if closed

        for item_index, item_name in enumerate(tuple(self._testbed_info[stub_type.value].keys())[: index + 1]):
            item_info = self._testbed_info[stub_type.value][item_name]

            if item_index < len(storage.clients[stub_type]):
                # Already created client. Check if closed
                if storage.clients[stub_type][item_index].closed:
                    # Reopen
                    storage.clients[stub_type][item_index].stub = self._com_handler.create_client(
                        stub_type.value, item_info.address, item_info.port
                    )
                    storage.clients[stub_type][item_index].closed = False
            else:
                # Need to create
                stub = self._com_handler.create_client(stub_type.value, item_info.address, item_info.port)
                storage.clients[stub_type].append(Client(item_name, stub))

        return storage.clients[stub_type][index].stub

    def close_client(self, stub: RanStub) -> None:
        for client_array in storage.clients.values():
            for client in client_array:
                if client.stub is stub:
                    return self._call_close_client(client)
        raise KeyError("Client was never created")

    def close_all(self) -> None:
        failures = False
        for client_array in storage.clients.values():
            for client in client_array:
                if not client.closed:
                    try:
                        logging.debug("Closing %s [%s]", client.name, id(client.stub))
                        self._call_close_client(client)
                    except Exception as err:  # pylint: disable=broad-exception-caught
                        failures = True
                        logging.error("Failure closing the client:")
                        logging.exception(err)
                else:
                    logging.warning("%s [%s] already closed", client.name, id(client.stub))
        if failures:
            raise RuntimeError("Failures closing clients")

    def _call_close_client(self, client: Client) -> None:
        if not client.closed:
            self._com_handler.close_client(client.stub)
            client.closed = True
