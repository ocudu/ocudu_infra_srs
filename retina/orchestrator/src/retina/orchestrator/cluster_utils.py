#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Cluster utilities
"""

import logging
from enum import Enum
from time import sleep
from typing import Union

from retina.orchestrator import configs
from retina.orchestrator.retina_kubernetes import Kubernetes
from retina.orchestrator.utils import get_package_version

CONFIGMAP_NAME_RETINA_VERSION = "retina-version"
RETINA_ADMIN_NAME = "retina-admin"


class ResourceType(Enum):
    """
    Resource type
    """

    NODE = "node"
    CLUSTER_RESOURCE = "cluster-resource"
    NODE_RESOURCE = "node-resource"


def set_retina_version(k_server: Kubernetes, new_version: str):
    """
    Set retina version
    """
    config_map_config = configs.ConfigmapConfig(
        orch_id=RETINA_ADMIN_NAME,
        user_name=RETINA_ADMIN_NAME,
        timeout=None,
        data={CONFIGMAP_NAME_RETINA_VERSION: new_version},
        name=CONFIGMAP_NAME_RETINA_VERSION,
    )

    for _ in range(3):
        k_server.delete_config_map(CONFIGMAP_NAME_RETINA_VERSION)
        sleep(1)

        if k_server.config_map_exists(CONFIGMAP_NAME_RETINA_VERSION):
            break

    k_server.create_config_map(config_map_config)
    for _ in range(3):
        if k_server.config_map_exists(CONFIGMAP_NAME_RETINA_VERSION):
            break
        sleep(1)

    return new_version


def get_retina_version(k_server: Kubernetes) -> Union[str, None]:
    """
    Get retina version
    """
    try:
        config_map = k_server.get_config_map(CONFIGMAP_NAME_RETINA_VERSION)
        if config_map is None or config_map.data is None:
            return "0.0.0"
        return config_map.data[CONFIGMAP_NAME_RETINA_VERSION]
    except KeyError:
        return None


def check_if_update_needed(k_server: Kubernetes) -> bool:
    """
    Check if update is needed
    """
    current_package_version = get_package_version()
    retina_cluster_version = get_retina_version(k_server)

    if retina_cluster_version and current_package_version != retina_cluster_version:
        logging.warning(
            "Please update Retina. Current package version: %s, latest version: %s",
            current_package_version,
            retina_cluster_version,
        )
        return True
    return False
