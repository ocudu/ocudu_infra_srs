# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Port interface for parsing and processing the client version
"""

from abc import abstractmethod

from retina.client.core.communication_port import CommunicationPort
from retina.protocol import RanClient


class IncompatibleRetinaVersion(Exception):
    """
    Current client and agent are incompatible
    """


class VersionPort:
    # pylint: disable=too-few-public-methods
    """
    Port interface for parsing and processing the client version
    """

    def __init__(self, com_handler: CommunicationPort, *args, **kwargs) -> None:
        self._com_handler = com_handler
        super().__init__(*args, **kwargs)

    @abstractmethod
    def validate_client_version(self, stub: RanClient) -> None:
        """
        Check if client version is compatible with this client.
        Raises IncompatibleRetinaVersion if they're not compatible
        """
