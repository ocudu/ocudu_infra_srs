# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
UE Simulator Base
"""

from abc import ABCMeta, abstractmethod

import grpc
from google.protobuf.empty_pb2 import Empty
from retina.protocol.base_pb2 import UEDefinition
from retina.protocol.ue_pb2 import UEStartInfo
from retina.protocol.ue_simulator_pb2_grpc import UESimulatorServicer

from retina.agent.drivers.base import BaseDriver
from retina.agent.drivers.ue import build_ue_definition


class UESimulatorDriver(UESimulatorServicer, BaseDriver, metaclass=ABCMeta):
    """
    UE Simulator Base Driver.
    The simulator itself (and not Retina) drives the simulated UEs, so there is no per-client subscriber.
    """

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> UEDefinition:
        return build_ue_definition()

    @abstractmethod
    def Start(self, request: UEStartInfo, context: grpc.ServicerContext) -> Empty:
        """Start the simulation. Raise an error if it can't be started."""
