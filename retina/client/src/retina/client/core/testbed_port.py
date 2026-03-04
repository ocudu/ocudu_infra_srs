# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Port interface for parsing and processing testbed inputs
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Dict, OrderedDict

from retina.protocol import RanStub
from retina.protocol.channel_emulator_pb2_grpc import ChannelEmulatorStub
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import CUStub, DUStub, GNBStub
from retina.protocol.ric_pb2_grpc import NearRtRicStub
from retina.protocol.ue_pb2_grpc import UEStub

from retina.client.core.communication_port import CommunicationPort


@dataclass(frozen=True)
class NodeInfo:
    """
    Represents basic information about each node available in the testbed
    """

    address: str
    port: int
    resources: list


class TestbedPort:
    """
    Port interface for parsing and processing testbed inputs
    """

    def __init__(self, com_handler: CommunicationPort, *args, **kwargs) -> None:
        self._com_handler = com_handler
        super().__init__(*args, **kwargs)

    @abstractmethod
    def validate_testbed(self, testbed: Dict) -> None:
        """
        Validate and parse testbed information
        """

    @abstractmethod
    def get_ue(self, index: int = 0) -> UEStub:
        """
        Return a UE stub in the specified index.
        If not exists, raises an Exception.
        """

    @abstractmethod
    def get_gnb(self, index: int = 0) -> GNBStub:
        """
        Return a gnb stub in the specified index.
        If not exists, raises an Exception.
        """

    @abstractmethod
    def get_cu(self, index: int = 0) -> CUStub:
        """
        Return a cu stub in the specified index.
        If not exists, raises an Exception.
        """

    @abstractmethod
    def get_du(self, index: int = 0) -> DUStub:
        """
        Return a du stub in the specified index.
        If not exists, raises an Exception.
        """

    @abstractmethod
    def get_5gc(self, index: int = 0) -> FiveGCStub:
        """
        Return a 5gc stub in the specified index.
        If not exists, raises an Exception.
        """

    @abstractmethod
    def get_ric(self, index: int = 0) -> NearRtRicStub:
        """
        Return a RIC stub in the specified index.
        If not exists, raises an Exception.
        """

    @abstractmethod
    def get_channel_emulator(self, index: int = 0) -> ChannelEmulatorStub:
        """
        Return a Channel Emulator stub in the specified index.
        If not exists, raises an Exception.
        """

    @abstractmethod
    def close_client(self, stub: RanStub) -> None:
        """
        Close client for specified
        """

    @abstractmethod
    def close_all(self) -> None:
        """
        Close all clients
        """

    @abstractmethod
    def get_testbed_info(self) -> Dict[str, OrderedDict[str, NodeInfo]]:
        """
        Get testbed info
        """
