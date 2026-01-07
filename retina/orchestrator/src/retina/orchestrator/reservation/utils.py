#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Utils for reservation
"""

import base64
import json
import time
from pathlib import Path
from typing import Any

import yaml

from retina.orchestrator import configs, const
from retina.orchestrator.const import CLUSTER_CONFIGURATION_CONFIGMAP_NAME
from retina.orchestrator.srs_kubernetes import ErrorCode, Kubernetes
from retina.orchestrator.utils import get_current_time


# pylint: disable=too-many-arguments, disable=too-many-positional-arguments
def reserve_cluster_resource_configmap(
    k_server: Kubernetes, name: str, capacity_number: int, orch_id: str, user_name: str, timeout: int
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
        name=get_cluster_resource_name(name, capacity_number),
    )

    response = k_server.create_config_map(config_map_config)
    result = False
    if response == ErrorCode.OK:
        result = True
    return result


def unlock_cluster_resource(k_server: Kubernetes, name: str, capacity_number: int) -> bool:
    """
    Unlock cluster resource
    """
    config_map_name = get_cluster_resource_name(name, capacity_number)
    response = k_server.delete_config_map(config_map_name)
    result = False
    if response == ErrorCode.OK:
        result = True
    return result


def get_cluster_resource_name(name: str, capacity_number: int):
    """
    Get cluster resource name for configmap
    """
    return f"{const.CLUSTER_RESOURCE_SPACE_PREFIX}-{name}-{str(capacity_number)}"


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


def unlock_resource_space(k_server: Kubernetes, number: int):
    """
    Unlock cluster resource
    """
    config_map_name = get_space_name(number)
    response = k_server.delete_config_map(config_map_name)
    result = False
    if response == ErrorCode.OK:
        result = True
    return result


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


def deploy_server(config_path: Path, k_server: Kubernetes):
    """
    Deploy Kubernetes cluster
    """
    with open(str(config_path), encoding="UTF-8") as file:
        conf = yaml.load(file, Loader=yaml.FullLoader)

    current_date = get_current_time()
    resource_list = base64.b64encode(json.dumps(conf["nodes"]).encode("ascii")).decode("ascii")
    cluster_resource_list = base64.b64encode(json.dumps(conf["cluster_resource_list"]).encode("ascii")).decode("ascii")

    data = {
        "update-time": current_date,
        "version": conf["global"]["version"],
        "networking-mode": conf["global"]["networking-mode"],
        "dnsPolicy": conf["global"]["dnsPolicy"],
        "resource": resource_list,
        "cluster_resource_list": cluster_resource_list,
    }
    config_map_config = configs.ConfigmapConfig(
        orch_id="srsretinaadmin",
        user_name="srsretinaadmin",
        timeout=None,
        data=data,
        name=CLUSTER_CONFIGURATION_CONFIGMAP_NAME,
    )

    k_server.delete_config_map(CLUSTER_CONFIGURATION_CONFIGMAP_NAME)
    while k_server.config_map_exists(CLUSTER_CONFIGURATION_CONFIGMAP_NAME):
        time.sleep(1)
    k_server.create_config_map(config_map_config)


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
    capacity_number: int,
):
    """
    Get user name cluster resource reservation
    """
    try:
        configmap_data = k_server.get_config_map(get_cluster_resource_name(resource_name, capacity_number)).data
        user_name = configmap_data["user_name"]  # type: ignore
        return user_name
    except Exception:  # pylint: disable=broad-except
        return ""
