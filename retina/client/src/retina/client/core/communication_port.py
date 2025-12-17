#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Handle Retina Communication with the agent. Port
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from retina.protocol import RanStub


@dataclass(frozen=True)
class Version:
    """
    Retina Agent Version
    """

    agent: str
    sut: str


class CommunicationPort:
    """
    Handle Retina Communication with the agent. Port
    """

    @abstractmethod
    def create_client(self, node_type: str, *com_args) -> RanStub:
        """
        Create a client for the specified agent.
        Raises an Exception if can't be created
        """

    @abstractmethod
    def get_version(self, stub: RanStub) -> Version:
        """
        Get Agent and SUT version
        """

    @staticmethod
    @abstractmethod
    def push_parameter(stub: RanStub, key: str, value: Any, param_namespace: str) -> None:
        """
        Send a parameter to the agent
        """

    @abstractmethod
    def close_client(self, stub: RanStub) -> None:
        """
        Close client connection
        Raises an Exception if can't be closed
        """

    @staticmethod
    @abstractmethod
    def download_artifacts(stub: RanStub, report_folder: str) -> None:
        """
        Download artifacts from agent
        """

    @staticmethod
    @abstractmethod
    def get_artifact_id(stub: RanStub) -> str:
        """
        Get artifact ID
        """
