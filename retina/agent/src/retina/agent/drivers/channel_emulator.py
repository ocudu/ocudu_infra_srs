#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Channel Emulator Base
"""

from abc import ABCMeta

import grpc
from google.protobuf.empty_pb2 import Empty
from retina.protocol.base_pb2 import ChannelEmulatorDefinition, ChannelEmulatorType
from retina.protocol.channel_emulator_pb2_grpc import ChannelEmulatorServicer

from retina.agent.drivers.base import BaseDriver
from retina.agent.parameters import testbed_defaults


class ChannelEmulatorDriver(ChannelEmulatorServicer, BaseDriver, metaclass=ABCMeta):
    """
    Channel Emulator Driver
    """

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> ChannelEmulatorDefinition:
        return ChannelEmulatorDefinition(
            type=ChannelEmulatorType.UNKNOWN,
            zmq_ip=testbed_defaults.ip_zmq,
            dl_zmq_port=testbed_defaults.port_array[0],
            ul_zmq_port=testbed_defaults.port_array[1],
        )
