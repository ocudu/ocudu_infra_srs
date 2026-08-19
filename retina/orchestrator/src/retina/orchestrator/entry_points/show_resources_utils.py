# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Entrypoint to show cluster resources.
"""

import contextlib
import re
from typing import Dict, List

from rich.console import Console
from rich.table import Table

from retina.orchestrator.elements import Node
from retina.orchestrator.entry_points.utils import (
    GITLAB_RUNNER_NAMESPACE,
    GITLAB_RUNNER_POD_PREFIX,
    set_default_colored_logger,
)
from retina.orchestrator.reservation import transformations as ts
from retina.orchestrator.reservation.managers import get_resources_in_cluster
from retina.orchestrator.reservation.resources import ClusterResource, NodeResource
from retina.orchestrator.reservation.utils import check_cluster_resource_user_reservation, check_space_user_reservation
from retina.orchestrator.retina_kubernetes import DEFAULT_NAMESPACE, Kubernetes, PodStatus

# K8s quantity suffix to bytes multiplier, binary and decimal
SUFFIX_MULTIPLIER = {
    "": 1,
    "ki": 1024,
    "mi": 1024**2,
    "gi": 1024**3,
    "ti": 1024**4,
    "k": 10**3,
    "m": 10**6,
    "g": 10**9,
    "t": 10**12,
}


def convert_to_gi(size_str):
    """
    Convert a Kubernetes quantity to Gi
    """
    with contextlib.suppress(Exception):
        match = re.fullmatch(r"\s*([\d.]+)\s*([a-zA-Z]*)\s*", size_str)
        if match is not None:
            return round(float(match.group(1)) * SUFFIX_MULTIPLIER[match.group(2).lower()] / 1024**3, 2)
    return None


def print_info(cluster_info, verbose):
    """
    Print resource table
    """
    if not verbose:
        return
    table = Table(title="Cluster info")

    table.add_column("Networking mode", style="magenta")
    table.add_column("Last update", style="magenta")
    table.add_column("Version", style="magenta")

    table.add_row(
        cluster_info["networking-mode"],
        cluster_info["update-time"],
        cluster_info["version"],
    )

    console = Console()
    console.print(table)


def print_cluster_resources(cluster_resource_list: List[ClusterResource], k_server: Kubernetes):
    """
    Print resource table
    """
    table = Table()

    table.add_column("Name ID", justify="right", style="cyan")
    table.add_column("Reserved by", style="yellow")
    table.add_column("Resource type", style="magenta")
    table.add_column("Resource model", style="magenta")

    for resource in sorted(cluster_resource_list, key=lambda x: x.get_full_name()):
        resource_type = resource.type_r
        resource_model = resource.model
        name = resource.get_full_name()

        resource_reservation_user = check_cluster_resource_user_reservation(k_server=k_server, resource_name=name)
        table.add_row(
            name,
            resource_reservation_user,
            resource_type,
            resource_model,
        )

    console = Console()
    console.print(table)


def print_node_resources(resource_list: List[NodeResource], k_server: Kubernetes):
    """
    Print resource table
    """
    table = Table()

    table.add_column("Name ID", style="magenta")
    table.add_column("Node name", justify="right", style="cyan")
    table.add_column("Reserved by", style="yellow")
    table.add_column("R.Space", style="magenta")
    table.add_column("Arguments", style="magenta")

    for resource in sorted(resource_list, key=lambda x: (x.space, x.get_full_name())):
        node_name = resource.node.name if resource.node is not None else ""
        arguments = getattr(resource, "args", "")

        resource_space = str(resource.space)
        resource_reservation_user = check_space_user_reservation(k_server=k_server, space=resource.space or 0)
        table.add_row(
            resource.get_full_name(),
            node_name,
            str(resource_reservation_user),
            resource_space,
            arguments,
        )

    console = Console()
    console.print(table)


def print_nodes(k_server: Kubernetes, retina_node_dict: Dict[str, Node], verbose: bool):
    """
    Print resource table
    """
    table = Table()

    table.add_column("Node name ID", justify="right", style="cyan")
    table.add_column("Reserved by", style="yellow")
    table.add_column("IP", style="magenta")
    table.add_column("Architecture", style="magenta")

    pods_running_in_cluster = k_server.search_pods(
        status_array=[PodStatus.RUNNING.value], namespace_array=[DEFAULT_NAMESPACE, GITLAB_RUNNER_NAMESPACE]
    )

    if verbose:
        table.add_column("CPU", style="magenta")
        table.add_column("Memory (Gi)", style="magenta")
        table.add_column("Storage (Gi)", style="magenta")
        table.add_column("Label List", style="magenta")
        table.add_column("Taint List", style="magenta")

    for name, retina_node in retina_node_dict.items():
        memory = str(convert_to_gi(retina_node.allocatable_memory))
        storage = str(convert_to_gi(retina_node.allocatable_storage))
        retina_label_list_str = ", ".join(f"{element.name}={element.value}" for element in retina_node.label_list)
        taint_list = retina_node.taint_list

        # Get user list in node
        user_list = []
        for pod in [pod for pod in pods_running_in_cluster if pod.spec.node_name == name]:
            if pod.metadata.name.startswith(GITLAB_RUNNER_POD_PREFIX):
                continue
            if pod.metadata.annotations and "user_name" in pod.metadata.annotations:
                user_list.append(pod.metadata.annotations["user_name"])
            if GITLAB_RUNNER_NAMESPACE in pod.metadata.namespace:
                user_list.append("gitlab-runner")
        clean_user_list = list(set(user_list))

        if verbose:
            table.add_row(
                name,
                ", ".join(clean_user_list),
                retina_node.ip_address,
                retina_node.architecture,
                str(retina_node.allocatable_cpu),
                memory,
                storage,
                retina_label_list_str,
                ", ".join([obj.get_str_taint() for obj in taint_list]),
            )
        else:
            table.add_row(name, ", ".join(clean_user_list), retina_node.ip_address, retina_node.architecture)

    console = Console()
    console.print(table)


def show_resources(verbose: bool, in_cluster: bool = False):
    """
    Entrypoint to show cluster resources.

    Args:
        verbose (bool): Enable verbose output
        in_cluster (bool): Whether to run in Kubernetes cluster mode
    """
    set_default_colored_logger()

    k_server = Kubernetes(is_incluster=in_cluster)

    cluster_info = k_server.get_cluster_configuration()

    resource_list = get_resources_in_cluster(k_server)
    node_resources = ts.get_typed_node_resources(resource_list)
    cluster_resources = ts.get_typed_cluster_resources(resource_list)

    retina_node_dict = k_server.get_retina_node_dict(True, False)

    print_info(cluster_info, verbose)
    print_cluster_resources(cluster_resources, k_server)
    if verbose:
        print_node_resources(node_resources, k_server)
    print_nodes(k_server, retina_node_dict, verbose)
