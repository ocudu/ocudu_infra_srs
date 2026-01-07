#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Process and store available resources for the Retina agent.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from retina.protocol.resource import (
    Accelerator,
    API,
    Core,
    License,
    load_resources_from_file,
    Node,
    Remote,
    Ru,
    Sdr,
    Ue,
)


@dataclass
class AvailableResources:  # pylint: disable=too-many-instance-attributes
    """Dataclass to hold available resources."""

    address: str = os.getenv("RETINA_IP", "")
    node: Optional[Node] = None
    remote: Optional[Remote] = None
    core: Optional[Core] = None
    api: Optional[API] = None
    license: Optional[License] = None
    ue: Optional[Ue] = None
    sdr: Optional[Sdr] = None
    ru: Optional[Ru] = None
    accelerator: Optional[Accelerator] = None


class ResourceManager:
    """
    Manages resources for the Retina agent.
    """

    _available_resources: AvailableResources

    @classmethod
    def load_resources(cls, resource_folder: Union[str, Path]) -> None:
        """
        Load resources from the specified folder.
        :param resource_folder: Path to the resource folder.
        """
        resource_folder = Path(resource_folder)
        if not resource_folder.exists() or not resource_folder.is_dir():
            raise FileNotFoundError(f"Resource folder {resource_folder} does not exist or is not a directory.")

        cls._available_resources = AvailableResources()
        for resource_file in resource_folder.glob("*.y*ml"):
            logging.info("Loading resources from %s", resource_file)
            for resource in load_resources_from_file(resource_file):
                field_name = str(resource.__class__.__name__).lower()
                if not hasattr(cls._available_resources, field_name):
                    raise ValueError(f"Unknown resource type: {field_name} in file {resource_file}")
                setattr(cls._available_resources, field_name, resource)

    @classmethod
    def get_resources(cls) -> AvailableResources:
        """
        Get the available resources.
        :return: AvailableResources dataclass instance.
        :raises ValueError: If resources haven't been loaded yet.
        """
        if not hasattr(cls, "_available_resources") or cls._available_resources is None:
            raise ValueError("Resources not loaded. Call load_resources() first.")
        return cls._available_resources
