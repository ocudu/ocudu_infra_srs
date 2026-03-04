# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
In charge of parsing and processing the client version
"""

import logging

from retina.protocol import RanStub

import retina.client
from retina.client.core.version_port import VersionPort

try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version  # type: ignore


class VersionService(VersionPort):
    """
    In charge of parsing and processing the client version
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, *args, **kwargs) -> None:
        self._client_version = version(retina.client.__name__).split(".")
        super().__init__(*args, **kwargs)

    def validate_client_version(self, stub: RanStub) -> None:
        agent_version = self._com_handler.get_version(stub).agent.split(".")
        is_compatible = False
        if self._client_version[0] == agent_version[0] and self._client_version[1] >= agent_version[1]:
            is_compatible = True
        if not is_compatible:
            logging.warning("Client version is %s while agent version is %s", self._client_version, agent_version)
