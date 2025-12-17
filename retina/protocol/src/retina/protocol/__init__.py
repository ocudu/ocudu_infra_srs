#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Shortcuts
"""

from typing import Union

from retina.protocol.base_pb2_grpc import BaseStub
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import GNBStub
from retina.protocol.ue_pb2_grpc import UEStub

RanStub = Union[UEStub, GNBStub, FiveGCStub, BaseStub]
