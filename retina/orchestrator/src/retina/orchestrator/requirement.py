# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Requirement manager
"""

from dataclasses import dataclass
from typing import Dict, List, Sequence, Union

from retina.orchestrator.elements import LabelDefinition

RETINA_PREFIX = "retina"

ROUNDING_FRACTIONAL = "fractional"
ROUNDING_ROUND = "round"
ROUNDING_TRUNCATE = "truncate"
ROUNDING_MODES = (ROUNDING_FRACTIONAL, ROUNDING_ROUND, ROUNDING_TRUNCATE)
# Whole cores only make sense for cpu
ROUNDING_RESOURCES = ("cpu",)


@dataclass
class RequirementDefinition:
    """
    Requests definition
    """

    name: str
    requests: Union[str, int, None]
    limits: Union[str, int, None]
    rounding: str = ROUNDING_FRACTIONAL


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

    def get_label_list(self) -> List[LabelDefinition]:
        """
        Get labels
        """
        return self.label_list

    def add_pod_req(self, key: str, value: Dict):
        """
        Add requests in the POD
        """
        rounding = value.get("rounding", ROUNDING_FRACTIONAL)
        if rounding not in ROUNDING_MODES:
            raise ValueError(f"Invalid rounding '{rounding}' for '{key}', expected one of {ROUNDING_MODES}")
        if rounding != ROUNDING_FRACTIONAL and key not in ROUNDING_RESOURCES:
            raise ValueError(f"Rounding is only supported for {ROUNDING_RESOURCES}, not '{key}'")
        req = RequirementDefinition(key, value.get("requests", None), value.get("limits", None), rounding)
        self.req_list.append(req)
