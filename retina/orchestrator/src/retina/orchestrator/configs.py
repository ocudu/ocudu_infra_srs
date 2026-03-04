# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Configs
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from retina.orchestrator.elements import TaintDefinition
from retina.orchestrator.requirement import LabelDefinition, RequirementDefinition


@dataclass()
class RetinaBaseConfig:
    """
    Data class for retina base config
    """

    name: str
    orch_id: str
    user_name: str
    timeout: Optional[int]


@dataclass()
# pylint: disable=too-many-instance-attributes
class PodConfig(RetinaBaseConfig):
    """
    Data class for pod config
    """

    dns_policy: str
    image: str
    resource_data_configmap_list: List[str]
    retina_ports: List[int]
    extra_ports: List[int]
    privileged: bool
    taint_list: List[TaintDefinition]
    label_list: List[LabelDefinition]
    request_list: List[RequirementDefinition]
    node_name: Optional[str]
    enable_usb_connection: bool
    enable_pci_connection: bool
    enable_network_connection: str
    environment: List[Dict]
    command: Optional[List[str]]
    not_finite_execution: Optional[bool]
    grace_period: float


@dataclass()
# pylint: disable=too-many-instance-attributes
class ConfigmapConfig(RetinaBaseConfig):
    """
    Data class for configmap config
    """

    data: Dict
