# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
RIC Base
"""

from abc import ABCMeta

import grpc
from google.protobuf.empty_pb2 import Empty
from retina.protocol.base_pb2 import NearRtRicDefinition
from retina.protocol.ric_pb2_grpc import NearRtRicServicer

from retina.agent.drivers.base import BaseDriver
from retina.agent.parameters import testbed_defaults


class NearRtRicDriver(NearRtRicServicer, BaseDriver, metaclass=ABCMeta):
    """
    RIC Driver
    """

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> NearRtRicDefinition:
        return NearRtRicDefinition(
            enabled=1,
            ric_ip=testbed_defaults.ip,
            ric_port=testbed_defaults.port_array[0],
        )
