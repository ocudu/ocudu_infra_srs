# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
GNB Base
"""

from abc import ABCMeta

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import CUCPDefinition, CUUPDefinition, DUDefinition
from retina.protocol.gnb_pb2_grpc import CUCPServicer, CUServicer, CUUPServicer, DUServicer, GNBServicer

from retina.agent.drivers.base import BaseDriver
from retina.agent.parameters import gnb_defaults, testbed_defaults


class CUCPDriver(CUCPServicer, BaseDriver, metaclass=ABCMeta):
    """
    CU-CP Base Driver
    """

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> CUCPDefinition:
        return CUCPDefinition(
            cucp_ip=testbed_defaults.ip,
            cucp_port=38472,  # F1AP port, see TS 38.472, section 7.
        )


class CUUPDriver(CUUPServicer, BaseDriver, metaclass=ABCMeta):
    """
    CU-UP Base Driver
    """

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> CUUPDefinition:
        return CUUPDefinition(
            cuup_ip=testbed_defaults.ip,
            e1_port=38462,  # E1AP port, see TS 38.463.
        )


class CUDriver(CUServicer, BaseDriver, metaclass=ABCMeta):
    """
    CU Base Driver
    """

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> CUCPDefinition:
        return CUCPDefinition(
            cucp_ip=testbed_defaults.ip,
            cucp_port=38472,  # F1AP port, see TS 38.472, section 7.
        )


class DUDriver(DUServicer, BaseDriver, metaclass=ABCMeta):
    """
    DU Base Driver
    """

    def GetDefinition(
        self, request: UInt32Value, context: grpc.ServicerContext
    ) -> DUDefinition:  # UInt32Value is the cell offset.
        return DUDefinition(
            zmq_ip=testbed_defaults.ip_zmq,
            zmq_port_array=[
                testbed_defaults.port_array[request.value + i]
                for i in range(gnb_defaults.num_cells * max(gnb_defaults.nof_antennas_dl, gnb_defaults.nof_antennas_ul))
            ],
        )


class GNBDriver(GNBServicer, BaseDriver, metaclass=ABCMeta):
    """
    GNB Base Driver
    """

    def GetDefinition(
        self, request: UInt32Value, context: grpc.ServicerContext
    ) -> DUDefinition:  # UInt32Value is the DU cell offset.
        return DUDriver.GetDefinition(self, request, context)
