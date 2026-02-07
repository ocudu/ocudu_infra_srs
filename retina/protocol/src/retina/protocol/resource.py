#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Model classes for resources used in the testbed configuration.
"""

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Type, Union

import yaml


class _ResourceSerializer:
    """Complete serializer for Resource objects"""

    _registry: Dict[str, Type] = {}

    @classmethod
    def register(cls, dataclass_type: Type) -> None:
        """Register a dataclass type for serialization"""
        cls._registry[dataclass_type.__name__.lower()] = dataclass_type

    @classmethod
    def to_dict(cls, obj: Any) -> Dict[str, Any]:
        """Convert Resource object to dictionary with type"""
        if hasattr(obj, "__dataclass_fields__"):
            result = asdict(obj)
            result["type"] = obj.__class__.__name__
            return result
        return vars(obj)  # type: ignore

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Any:
        """Create object from dictionary with type"""

        if not isinstance(data, dict) or "type" not in data:
            return data

        class_name = data.pop("type").lower()
        if class_name not in cls._registry:
            raise ValueError(f"Type '{class_name}' not registered")

        target_class = cls._registry[class_name]

        # Get type hints for the constructor
        field_names = {f.name for f in fields(target_class)}

        # Process each field according to its expected type
        processed_args = {}
        for field_name, field_value in data.items():
            if field_name not in field_names:
                continue

            if isinstance(field_value, dict) and "type" in field_value:
                # Child object with type
                processed_args[field_name] = cls.from_dict(field_value)
            elif isinstance(field_value, list):
                # List that may contain typed objects
                processed_list = []
                for item in field_value:
                    if isinstance(item, dict) and "type" in item:
                        processed_list.append(cls.from_dict(item))
                    else:
                        processed_list.append(item)
                processed_args[field_name] = processed_list
            else:
                processed_args[field_name] = field_value

        return target_class(**processed_args)


class _ResourceLoader(yaml.SafeLoader):  # pylint: disable=too-many-ancestors
    """Custom YAML loader that automatically deserializes Resource objects."""


def _construct_resource(loader, node):
    """Constructor for resource objects with type field."""
    # Construct the mapping normally with deep=True to ensure nested structures are built
    mapping = loader.construct_mapping(node, deep=True)

    # Try to deserialize if it has a type field
    if isinstance(mapping, dict) and "type" in mapping:
        try:
            return _ResourceSerializer.from_dict(mapping)
        except (ValueError, TypeError):
            return mapping

    return mapping


# Register a constructor for mappings that will check for resource type
_ResourceLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_resource)


def resource(cls):
    """Decorator that combines @resource with automatic registration"""
    cls = dataclass(cls, eq=True)
    _ResourceSerializer.register(cls)
    return cls


def dump_resource_list_to_str(resource_list: List) -> str:
    """
    Convert a list of Resource dataclasses to a list of dictionaries.
    :param resource_list: List of Resource dataclasses to convert.
    :return: List of dictionaries representing the resources.
    """
    return yaml.dump([_ResourceSerializer.to_dict(resource) for resource in resource_list])


def dump_resource_list_to_file(resource_list: List, file_path_str: str) -> None:
    """
    Dump resource to a YAML file.
    :param resource_list: List of Resource dataclasses to dump.
    :param file_path: Path to the output YAML file.
    """
    file_path = Path(file_path_str)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as fd:
        fd.write(dump_resource_list_to_str(resource_list))
        fd.flush()


def load_resources_from_file(file_path_str: Union[str, Path]) -> List[Any]:
    """
    Load resources from a YAML file.
    :param file_path: Path to the input YAML file.
    :return: List of deserialized Resource objects.
    """
    file_path = Path(file_path_str)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Resource file {file_path} does not exist or is not a file.")

    with file_path.open(encoding="utf-8") as file_descriptor:
        resource_data = yaml.load(file_descriptor, _ResourceLoader)

    if not isinstance(resource_data, list):
        raise ValueError(f"Resource file {file_path} does not contain a list of resources.")

    return resource_data


@resource
class Node:  # pylint: disable=too-few-public-methods
    """Node configuration."""

    use_node_ip: bool = field(default=False)  # pylint: disable=invalid-field-call
    port_array: List[int] = field(default_factory=list)  # pylint: disable=invalid-field-call
    lcores_eal: str = field(default="")  # pylint: disable=invalid-field-call


@resource
class Remote:  # pylint: disable=too-few-public-methods
    """Remote configuration."""

    address: str
    user: str
    password: str
    path: str


@resource
class License:  # pylint: disable=too-few-public-methods
    """License configuration."""

    address: str
    args: str


@resource
class API:  # pylint: disable=too-few-public-methods
    """API configuration."""

    address: str
    port: int


@resource
class Core:  # pylint: disable=too-few-public-methods
    """Core Network configuration."""

    address: str
    port: int
    mask: int


@resource
class Ue:  # pylint: disable=too-few-public-methods
    """Ue device configuration."""

    model: str
    serial_id: str
    imsi: str
    k: str
    amf: str
    opc: str
    adb_key: str


@resource
class Sdr:  # pylint: disable=too-few-public-methods
    """SDR configuration."""

    model: str
    args: str
    sample_rate: int
    tx_gain: int
    rx_gain: int
    sync: str


@resource
class Ru:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Radio Unit configuration."""

    model: str
    address: str
    network_interface: List[str]
    ru_mac_address: List[str]
    du_mac_address: List[str]
    vlan_tag_up: List[str]
    vlan_tag_cp: List[str]
    prach_port_id: str
    dl_port_id: str
    ul_port_id: str


@resource
class Accelerator:  # pylint: disable=too-few-public-methods
    """Accelerator configuration."""

    model: str
    id: int
    cb_mode: bool
    hwacc_type: str
    pdsch_enc_nof_hwacc: int
    pusch_dec_nof_hwacc: int
    harq_context_size: int
    args: str
