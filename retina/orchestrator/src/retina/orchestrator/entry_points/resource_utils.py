#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
This module contains the entry points for the reservation of cluster resources.
"""

from retina.orchestrator.reservation.utils import (
    reserve_cluster_resource_configmap,
    reserve_space_configmap,
    unlock_cluster_resource,
    unlock_resource_space,
)
from retina.orchestrator.retina_kubernetes import Kubernetes


def reserve_cluster_resource(k_server: Kubernetes, username: str, resource_id: str, timeout) -> bool:
    """
    Reserve a resource.
    """

    return reserve_cluster_resource_configmap(
        k_server=k_server,
        name=resource_id,
        orch_id="",
        user_name=username,
        timeout=timeout,
    )


def release_cluster_resource(k_server: Kubernetes, resource_id: str) -> bool:
    """
    Release a resource.
    """

    return unlock_cluster_resource(k_server=k_server, name=resource_id)


def reserve_resource_space(k_server: Kubernetes, space: int, user_name: str, timeout) -> bool:
    """
    Reserve a resource.
    """
    return reserve_space_configmap(k_server=k_server, space=space, orch_id="", user_name=user_name, timeout=timeout)


def release_resource_space(k_server: Kubernetes, space: int) -> bool:
    """
    Release a resource.
    """
    return unlock_resource_space(k_server=k_server, number=space)
