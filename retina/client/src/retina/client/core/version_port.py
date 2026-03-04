# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Port interface for parsing and processing the client version
"""

from abc import abstractmethod

from retina.protocol import RanStub

from retina.client.core.communication_port import CommunicationPort


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
    def validate_client_version(self, stub: RanStub) -> None:
        """
        Check if client version is compatible with this client.
        Raises IncompatibleRetinaVersion if they're not compatible
        """
