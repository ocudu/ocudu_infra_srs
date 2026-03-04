# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Requirement manager
"""

from dataclasses import dataclass
from typing import Dict, List, Sequence, Union

from retina.orchestrator.elements import LabelDefinition

RETINA_PREFIX = "retina"


@dataclass
class RequirementDefinition:
    """
    Requests definition
    """

    name: str
    requests: Union[str, int, None]
    limits: Union[str, int, None]


class RequirementManager:
    """
    Requirement manager
    """

    def __init__(self, config: Dict, additional_labels: Sequence[str]):
        """
        Constructor
        """
        self.label_list: List[LabelDefinition] = []
        self.req_list: List[RequirementDefinition] = []

        self.add_label("retina.srs.io/member=true")
        for label in additional_labels:
            self.add_label(label)
        for key, value in config.items():
            self.add_pod_req(key, value)

    def add_label(self, label: str):
        """
        Add label
        """
        key = label.split("=")[0]
        value = label.split("=")[1]
        self.label_list.append(LabelDefinition(key, value))

    def get_label_list(self):
        """
        Get labels
        """
        return self.label_list

    def add_pod_req(self, key: str, value: Dict):
        """
        Add requests in the POD
        """
        req = RequirementDefinition(key, value.get("requests", None), value.get("limits", None))
        self.req_list.append(req)
