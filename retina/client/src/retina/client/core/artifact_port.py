#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Port interface for artifact handling
"""

from abc import abstractmethod

from retina.protocol import RanStub

from retina.client.core.communication_port import CommunicationPort


class ArtifactPort:
    """
    Port interface for artifact handling
    """

    def __init__(self, com_handler: CommunicationPort, *args, **kwargs) -> None:
        self._com_handler = com_handler
        super().__init__(*args, **kwargs)

    @abstractmethod
    def download_client_artifacts(self, stub: RanStub, report_folder: str) -> None:
        """
        Download artifacts for the specified client
        """

    @abstractmethod
    def download_all_artifacts(self, report_folder: str) -> None:
        """
        Download all artifacts from agents in the test and save them in
        the report folder
        """
