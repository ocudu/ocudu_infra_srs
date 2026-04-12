# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Cluster utilities
"""

from enum import Enum
from time import sleep

from retina.orchestrator import configs
from retina.orchestrator.retina_kubernetes import Kubernetes

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
