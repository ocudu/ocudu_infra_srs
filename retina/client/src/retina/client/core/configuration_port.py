# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Port interface for handling configuration and parameters
"""

from abc import abstractmethod
from typing import Any, Dict, Optional

from retina.client.core.communication_port import CommunicationPort
from retina.protocol import RanClient


class ConfigurationPort:
    """
    Port interface for handling configuration and parameters
    """

    def __init__(self, com_handler: CommunicationPort, *args, **kwargs) -> None:
        self._com_handler = com_handler
        super().__init__(*args, **kwargs)

    @abstractmethod
    def validate_configuration(self, config_file_info: Dict) -> None:
        """
        Validate parameters information
        """

    @abstractmethod
    def register_template(self, kind: str, name: Optional[str], key: str, value: Any) -> None:
        """
        Save a template template_name:path to later push it to the client
        """

    @abstractmethod
    def register_parameter(self, kind: str, name: Optional[str], key: str, value: Any) -> None:
        """
        Save a parameter key:value to later push it to the client
        """

    @abstractmethod
    def push_client_config(self, stub: RanClient) -> None:
        """
        Send configured parameters to the client's agent
        """

    @abstractmethod
    def push_all_config(self) -> None:
        """
        Send all configured parameters to their agents
        """

    @abstractmethod
    def reset_all_config(self) -> None:
        """
        Clean up all related configuration / parameters info
        """
