# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Shortcuts
"""

# pylint: disable=too-few-public-methods

from typing import Union

from grpc_health.v1.health_pb2_grpc import HealthStub

from retina.protocol.base_pb2_grpc import BaseStub
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import (
    CUCPStub,
    CUStub,
    CUUPStub,
    DUStub,
    GNBStub,
)
from retina.protocol.ric_pb2_grpc import NearRtRicStub
from retina.protocol.ue_pb2_grpc import UEStub


class UEClient(UEStub, HealthStub, BaseStub):
    """UE agent stub — UE service methods + Base service methods."""

    def __init__(self, channel) -> None:
        BaseStub.__init__(self, channel)
        HealthStub.__init__(self, channel)
        UEStub.__init__(self, channel)


class GNBClient(GNBStub, HealthStub, BaseStub):
    """gNB agent stub — GNB service methods + Base service methods."""

    def __init__(self, channel) -> None:
        BaseStub.__init__(self, channel)
        HealthStub.__init__(self, channel)
        GNBStub.__init__(self, channel)


class CUClient(CUStub, HealthStub, BaseStub):
    """CU agent stub — CU service methods + Base service methods."""

    def __init__(self, channel) -> None:
        BaseStub.__init__(self, channel)
        HealthStub.__init__(self, channel)
        CUStub.__init__(self, channel)


class CUCPClient(CUCPStub, HealthStub, BaseStub):
    """CU-CP agent stub — CU-CP service methods + Base service methods."""

    def __init__(self, channel) -> None:
        BaseStub.__init__(self, channel)
        HealthStub.__init__(self, channel)
        CUCPStub.__init__(self, channel)


class CUUPClient(CUUPStub, HealthStub, BaseStub):
    """CU-UP agent stub — CU-UP service methods + Base service methods."""

    def __init__(self, channel) -> None:
        BaseStub.__init__(self, channel)
        HealthStub.__init__(self, channel)
        CUUPStub.__init__(self, channel)


class DUClient(DUStub, HealthStub, BaseStub):
    """DU agent stub — DU service methods + Base service methods."""

    def __init__(self, channel) -> None:
        BaseStub.__init__(self, channel)
        HealthStub.__init__(self, channel)
        DUStub.__init__(self, channel)


class FiveGCClient(FiveGCStub, HealthStub, BaseStub):
    """5GC agent stub — FiveGC service methods + Base service methods."""

    def __init__(self, channel) -> None:
        BaseStub.__init__(self, channel)
        HealthStub.__init__(self, channel)
        FiveGCStub.__init__(self, channel)


class NearRtRicClient(NearRtRicStub, HealthStub, BaseStub):
    """Near-RT RIC agent stub — NearRtRic service methods + Base service methods."""

    def __init__(self, channel) -> None:
        BaseStub.__init__(self, channel)
        HealthStub.__init__(self, channel)
        NearRtRicStub.__init__(self, channel)


RanClient = Union[
    UEClient,
    CUCPClient,
    CUUPClient,
    CUClient,
    DUClient,
    GNBClient,
    FiveGCClient,
    NearRtRicClient,
]
