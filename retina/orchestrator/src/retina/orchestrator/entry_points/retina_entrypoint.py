#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Retina CLI entry point.
"""

import logging
import sys
from typing import Dict, List

import click

import retina.orchestrator.reservation.transformations as ts
from retina.orchestrator.cluster_utils import check_if_update_needed
from retina.orchestrator.elements import Node
from retina.orchestrator.entry_points.dev_mode_utils import (
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_TIMEOUT,
    delete_orchestration_network_by_username,
    release_node,
    reserve_node,
)
from retina.orchestrator.entry_points.resource_utils import (
    release_cluster_resource,
    release_resource_space,
    reserve_cluster_resource,
    reserve_resource_space,
)
from retina.orchestrator.entry_points.show_resources_utils import show_resources
from retina.orchestrator.entry_points.utils import check_user_name, set_default_colored_logger
from retina.orchestrator.license_utils.license_utils import display_license_info
from retina.orchestrator.reservation.managers import get_resources_in_cluster
from retina.orchestrator.reservation.resources import ClusterResource, NodeResource
from retina.orchestrator.retina_kubernetes import Kubernetes
from retina.orchestrator.utils import get_retina_user

TIMEOUT = 20

set_default_colored_logger()


def get_list_of_resources(in_cluster=False) -> tuple[List[NodeResource], List[ClusterResource], Dict[str, Node]]:
    """
    Get the list of resources.

    Args:
        in_cluster (bool): Whether to run in Kubernetes cluster mode
    """
    k_server = Kubernetes(is_incluster=in_cluster)

    resource_list = get_resources_in_cluster(k_server)
    node_resources = ts.get_node_resources(resource_list).get_resources()
    cluster_resources = ts.get_cluster_resources(resource_list).get_resources()
    retina_node_dict = k_server.get_retina_node_dict(True, False)

    return node_resources, cluster_resources, retina_node_dict


def resource_is_in_cluster(
    resource_id: str,
    node_resources: List[NodeResource],
    cluster_resources: List[ClusterResource],
    retina_node_dict: Dict[str, Node],
) -> bool:
    """
    Check if the resource is in the cluster.
    """
    # cluster resource
    for resource in cluster_resources:
        if resource.get_full_name() == resource_id:
            return True

    # node resource
    for resource in node_resources:
        if resource.get_full_name() == resource_id:
            return True

    # node
    return resource_id in retina_node_dict


def check_if_resource_id_exists(
    resource_id_list: List[str],
    node_resources: List[NodeResource],
    cluster_resources: List[ClusterResource],
    retina_node_dict: Dict[str, Node],
) -> bool:
    """
    Check if the resource id exists.
    """
    for resource_id in resource_id_list:
        is_resource_id_exists = resource_is_in_cluster(resource_id, node_resources, cluster_resources, retina_node_dict)
        if not is_resource_id_exists:
            logging.error("Resource id %s does not exist", resource_id)
            sys.exit(1)
    return True


@click.group()
@click.option("--in-cluster", is_flag=True, help="Run in Kubernetes cluster mode")
@click.pass_context
def retina(ctx, in_cluster):
    """CLI for Retina system."""
    ctx.ensure_object(dict)
    ctx.obj["in_cluster"] = in_cluster


@retina.command()
@click.option("--verbose", type=bool, is_flag=True, default=False, help="Verbose mode")
@click.pass_context
def status(ctx, verbose):
    """Show all the resources in the cluster."""
    in_cluster = ctx.obj.get("in_cluster", False)

    display_license_info(Kubernetes(is_incluster=in_cluster), verbose)
    show_resources(verbose, in_cluster=in_cluster)


@retina.command()
@click.argument("resource", type=str, required=True)
@click.option("--username", type=str, default="", help="Your username")
@click.option("--verbose", type=bool, is_flag=True, default=False, help="Verbose mode")
@click.option("--image", type=str, default=DEFAULT_DOCKER_IMAGE, help="Image to use in node (dev mode)")
@click.option(
    "--loglevel",
    type=click.Choice(["info", "debug", "error", "warning"], case_sensitive=True),
    default="info",
    help="Log level",
)
@click.pass_context
def reserve(
    ctx, username, resource, verbose, image, loglevel
):  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    """Reserve a resource."""
    in_cluster = ctx.obj.get("in_cluster", False)

    if not username:
        username = get_retina_user()

    k_server = get_kubernetes_server(in_cluster)
    check_if_update_needed(k_server)

    logging.info("⏳ Reserving resource %s for user %s", resource, username)
    check_user_name(username)

    node_resources, cluster_resources, retina_node_dict = get_list_of_resources(in_cluster)
    resource_list_to_reserve = [resource.strip() for resource in resource.split(",")]

    # check if all the resources exist
    check_if_resource_id_exists(resource_list_to_reserve, node_resources, cluster_resources, retina_node_dict)

    reserved_resource_space = []

    for resource_inst in resource_list_to_reserve:
        result = False

        # node resource
        if resource_is_in_cluster(resource_inst, node_resources, [], {}):
            resource_space_to_reserve = resource_inst.split(":")[1]
            if not resource_space_to_reserve in reserved_resource_space:
                result = reserve_resource_space(k_server, int(resource_space_to_reserve), username, TIMEOUT)
        # cluster resource
        elif resource_is_in_cluster(resource_inst, [], cluster_resources, {}):
            result = reserve_cluster_resource(k_server, username, resource_inst, TIMEOUT)
        # node
        elif resource_is_in_cluster(resource_inst, [], [], retina_node_dict):
            logging.info("⏰ It may take up to %s minutes, please be patient...", DEFAULT_TIMEOUT // 60)
            result = reserve_node(k_server, resource_inst, username, verbose, image, loglevel)

        if result:
            logging.info("✅ Resource %s successfully reserved.", resource_inst)
        else:
            logging.error("❌ Resource %s not reserved.", resource_inst)


@retina.command()
@click.argument("resource", type=str, required=False)
@click.option("--username", type=str, help="It will release all the resources reserved by the user")
@click.pass_context
def release(ctx, username, resource):
    """Release a resource."""
    in_cluster = ctx.obj.get("in_cluster", False)

    if not username and not resource:
        raise click.UsageError("You must provide either a --username or a resource.")

    k_server = get_kubernetes_server(in_cluster)
    check_if_update_needed(k_server)

    logging.info("⏳ Releasing resource %s", resource if resource else "")
    check_user_name(username)

    if resource:
        node_resources, cluster_resources, retina_node_dict = get_list_of_resources(in_cluster)
        resource_list_to_reserve = [resource.strip() for resource in resource.split(",")]

        # check if all the resources exist
        check_if_resource_id_exists(resource_list_to_reserve, node_resources, cluster_resources, retina_node_dict)

        for resource_inst in resource_list_to_reserve:
            result = False
            # node resource
            if resource_is_in_cluster(resource_inst, node_resources, [], {}):
                result = release_resource_space(k_server, int(resource_inst.split(":")[1]))
            # cluster resource
            elif resource_is_in_cluster(resource_inst, [], cluster_resources, {}):
                result = release_cluster_resource(k_server, resource_inst)
            # node
            elif resource_is_in_cluster(resource_inst, [], [], retina_node_dict):
                release_node(k_server, resource_inst)
                result = True

            if result:
                logging.info("✅ Resource %s successfully released.", resource_inst)
            else:
                logging.error("❌ Resource %s not released.", resource_inst)

    if username:
        delete_orchestration_network_by_username(username, is_incluster=in_cluster)
        logging.info("✅ All resources reserved by user %s successfully released.", username)


def get_kubernetes_server(in_cluster=False):
    """
    Get the Kubernetes server.

    Args:
        in_cluster (bool): Whether to run in Kubernetes cluster mode
    """
    # pylint: disable=broad-exception-caught
    try:
        k_server = Kubernetes(is_incluster=in_cluster)
    except Exception:
        logging.error(
            "👎 Kubernetes server is down or your credentials are out of date. Please, contact with an administrator."
        )
        sys.exit(1)
    return k_server
