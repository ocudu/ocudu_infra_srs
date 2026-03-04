# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Shortcuts
"""

from typing import Union

from retina.protocol.base_pb2_grpc import BaseStub
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import GNBStub
from retina.protocol.ue_pb2_grpc import UEStub

RanStub = Union[UEStub, GNBStub, FiveGCStub, BaseStub]
