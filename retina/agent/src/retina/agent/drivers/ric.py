#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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
