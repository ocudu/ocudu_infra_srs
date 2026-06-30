# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Port interface for artifact handling
"""

from abc import abstractmethod

from retina.client.core.communication_port import CommunicationPort
from retina.protocol import RanClient


class ArtifactPort:
    """
    Port interface for artifact handling
    """

    def __init__(self, com_handler: CommunicationPort, *args, **kwargs) -> None:
        self._com_handler = com_handler
        super().__init__(*args, **kwargs)

    @abstractmethod
    def download_client_artifacts(self, stub: RanClient, report_folder: str) -> None:
        """
        Download artifacts for the specified client
        """

    @abstractmethod
    def download_all_artifacts(self, report_folder: str) -> None:
        """
        Download all artifacts from agents in the test and save them in
        the report folder
        """
