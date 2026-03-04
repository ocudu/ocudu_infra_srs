# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Store active Retina clients
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from retina.protocol import RanStub


@dataclass()
class Client:
    """
    Data class that stores channel and stub.
    In our approach, we'll have one and just one stub per channel.
    """

    name: str
    stub: RanStub
    closed: bool = False


class NodeTypeEnum(Enum):
    """
    Node types
    """

    UE = "ue"
    GNB = "gnb"
    CU = "cu"
    DU = "du"
    FIVEGC = "5gc"
    RIC = "ric"
    CHANNEL_EMULATOR = "channel-emulator"


clients: Dict[NodeTypeEnum, List[Client]] = {}
