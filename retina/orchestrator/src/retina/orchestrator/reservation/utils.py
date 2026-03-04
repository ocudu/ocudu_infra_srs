# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Utils for reservation
"""

from typing import Any

from retina.orchestrator import configs, const
from retina.orchestrator.retina_kubernetes import ErrorCode, Kubernetes


# pylint: disable=too-many-arguments, disable=too-many-positional-arguments
def reserve_cluster_resource_configmap(
    k_server: Kubernetes, name: str, orch_id: str, user_name: str, timeout: int
) -> bool:
    """
    Reserver cluster resource with configmap
    """
    data = {"orch_id": orch_id, "user_name": user_name}
    config_map_config = configs.ConfigmapConfig(
        orch_id=orch_id,
        user_name=user_name,
        timeout=timeout,
        data=data,
        name=get_cluster_resource_name(name),
    )

    response = k_server.create_config_map(config_map_config)
    result = False
    if response == ErrorCode.OK:
        result = True
    return result


def unlock_cluster_resource(k_server: Kubernetes, name: str) -> bool:
    """
    Unlock cluster resource
    """
    config_map_name = get_cluster_resource_name(name)
    return k_server.delete_config_map(config_map_name) == ErrorCode.OK


def get_cluster_resource_name(name: str):
    """
    Get cluster resource name for configmap
    """
    return f"{const.CLUSTER_RESOURCE_SPACE_PREFIX}-{name}"


def get_space_name(space):
    """
    Get space name for configmap
    """
    return f"{const.RESOURCE_SPACE_PREFIX}-{space}"


def reserve_space_configmap(k_server: Kubernetes, space: str, orch_id: str, user_name: str, timeout: int):
    """
    Reserver resource space with configmap
    """
    data = {"orch_id": orch_id, "user_name": user_name}
    config_map_config = configs.ConfigmapConfig(
        orch_id=orch_id, user_name=user_name, timeout=timeout, data=data, name=get_space_name(space)
    )

    response = k_server.create_config_map(config_map_config)
    result = False
    if response == ErrorCode.OK:
        result = True
    return result


def unlock_resource_space(k_server: Kubernetes, number: int) -> bool:
    """
    Unlock cluster resource
    """
    config_map_name = get_space_name(number)
    return k_server.delete_config_map(config_map_name) == ErrorCode.OK


def get_resource_data_configmap_name(obj: Any):
    """
    Get resource data configmap name
    """
    return const.RESOURCE_DATA_PREFIX + "-" + str(hash(obj))


def create_resource_data_configmap(
    k_server: Kubernetes, name: str, orch_id: str, user_name: str, data: dict, timeout: int
) -> bool:
    """
    Create resource data configmap
    """
    config_map_config = configs.ConfigmapConfig(
        orch_id=orch_id,
        user_name=user_name,
        timeout=timeout,
        data=data,
        name=name,
    )

    response = k_server.create_config_map(config_map_config)
    result = False
    if response == ErrorCode.OK:
        result = True
    return result


def check_if_space_is_available(k_server: Kubernetes, space: int):
    """
    Check is resource space is reserved
    """
    return not k_server.config_map_exists(get_space_name(str(space)))


def check_space_user_reservation(k_server: Kubernetes, space: int):
    """
    Get user name space reservation
    """
    try:
        configmap_data = k_server.get_config_map(get_space_name(space)).data
        user_name = configmap_data["user_name"]  # type: ignore
        return user_name
    except Exception:  # pylint: disable=broad-except
        return ""


def check_cluster_resource_user_reservation(
    k_server: Kubernetes,
    resource_name: str,
):
    """
    Get user name cluster resource reservation
    """
    try:
        configmap_data = k_server.get_config_map(get_cluster_resource_name(resource_name)).data
        user_name = configmap_data["user_name"]  # type: ignore
        return user_name
    except Exception:  # pylint: disable=broad-except
        return ""
