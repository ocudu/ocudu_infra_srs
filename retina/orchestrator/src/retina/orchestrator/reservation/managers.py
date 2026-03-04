# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Resources manager
"""

import logging
from random import shuffle
from time import sleep
from typing import Generator, List, Tuple

import retina.orchestrator.reservation.resources as rs
import retina.orchestrator.reservation.transformations as ts
from retina.orchestrator.const import RESERVATION_NUM_SECONDS_BETWEEN_RETRIES, TERMINATION_GRACE_PERIOD_SECONDS
from retina.orchestrator.elements import Node
from retina.orchestrator.requirement import RequirementManager
from retina.orchestrator.reservation import utils
from retina.orchestrator.reservation.utils import get_space_name
from retina.orchestrator.retina_kubernetes import Kubernetes
from retina.orchestrator.timeout_handler import TimeoutHandler


class PoolRequestReservation:
    """
    Pool request reservation
    """

    def __init__(
        self,
        request_reservation_list: List[rs.RequestReservation],
        binary_list: List[rs.BinaryDefinition],
        orch_id: str,
        user_name: str,
    ):
        self.request_reservation_list = request_reservation_list
        self.binary_list = binary_list
        self.orch_id = orch_id
        self.user_name = user_name

    def get_binaries(self) -> List[rs.BinaryDefinition]:
        """
        Get binaries
        """
        return self.binary_list

    def get_request_reservation_list(self) -> List[rs.RequestReservation]:
        """
        Get request reservation list
        """
        return self.request_reservation_list

    def get_all_resources(self) -> rs.ResourceList:
        """
        Get cluster resources
        """
        cluster_resources = []
        for request_reservation in self.request_reservation_list:
            resource_list = request_reservation.get_resources().get_resources()
            if request_reservation.requirement_manager.label_list:
                # If the user is requesting labels, we create a fake node to populate with the taints
                for resource in resource_list:
                    resource.node = Node(
                        name="",
                        architecture="",
                        os_image="",
                        kernel_version="",
                        label_list=request_reservation.requirement_manager.label_list,
                        taint_list=[],
                        ip_address="",
                        allocatable_cpu=0,
                        allocatable_memory="",
                        allocatable_storage="",
                    )
            cluster_resources.extend(resource_list)
        return rs.ResourceList(cluster_resources)

    def reserve_cluster_resources(self, kubernetes: Kubernetes, timeout_handler: TimeoutHandler):
        """
        Reserve cluster resources
        """
        # Reserve resources
        for request_reservation in self.request_reservation_list:
            result = reserve_cluster_resources(
                k_server=kubernetes,
                input_request=request_reservation.get_resources(),
                orch_id=self.orch_id,
                user_name=self.user_name,
                timeout_handler=timeout_handler,
            )
            request_reservation.add_reserved_resource_list(result)

    def reserve_node_resources(self, kubernetes: Kubernetes, timeout_handler: TimeoutHandler):
        """
        Reserve node resources
        """
        all_resources = self.get_all_resources()
        result = reserve_node_resources(
            k_server=kubernetes,
            input_request=all_resources,
            orch_id=self.orch_id,
            user_name=self.user_name,
            timeout_handler=timeout_handler,
        )
        # Assign the resources to the request reservation
        for request_reservation in self.request_reservation_list:
            reserved_resources_for_request = ts.get_resources_by_id(
                resource_list=result, id_def=request_reservation.name
            )
            request_reservation.add_reserved_resource_list(reserved_resources_for_request)


# pylint: disable=too-many-locals
def get_pool_request_reservation_from_config(
    config: List[dict], orch_id: str, user_name: str
) -> PoolRequestReservation:
    """
    Get pool request reservation from config
    """
    request_reservation_list: List[rs.RequestReservation] = []

    for config_inst in config:
        requirement_manager = RequirementManager(config_inst.get("requirements", {}), config_inst.get("labels", []))

        # Get resources
        resource_list: List[rs.ResourceType] = []
        for resource in config_inst.get("resources", []):
            resource_obj = rs.get_resource_from_config(resource)
            if resource_obj is not None:
                resource_list.append(resource_obj)

        # Get binaries
        binary_list: List[rs.BinaryDefinition] = []
        for b_inst in config_inst.get("shared_files", []):
            binary_list.append(
                rs.BinaryDefinition(
                    local_path=b_inst["local_path"],
                    remote_path=b_inst["remote_path"],
                    is_executable=b_inst["is_executable"],
                    is_optional=b_inst.get("is_optional", False),
                )
            )

        req = rs.RequestReservation(
            name=config_inst["name"],
            image=config_inst["image"],
            type_r=config_inst.get("type", ""),
            nof_ports=config_inst.get("nof_ports", 1),
            labels=config_inst.get("labels", []),
            resources=rs.ResourceList(resource_list),
            requirement_manager=requirement_manager,
            binary_list=binary_list,
            environment=config_inst.get("environment", []),
            enable_host_network_force=config_inst.get("host_network", ""),
            command=config_inst.get("command", None),
            force_external_ip=config_inst.get("force_external_ip", False),
            grace_period=config_inst.get("grace_period", TERMINATION_GRACE_PERIOD_SECONDS),
        )
        request_reservation_list.append(req)

    pool_request = PoolRequestReservation(
        request_reservation_list=request_reservation_list,
        orch_id=orch_id,
        user_name=user_name,
        binary_list=binary_list,
    )
    return pool_request


def reserve_node_resources(
    k_server: Kubernetes, input_request: rs.ResourceList, orch_id: str, user_name: str, timeout_handler: TimeoutHandler
) -> rs.ResourceList:
    """
    Node reservation
    """
    # Get node resources in request
    input_request_transform = ts.get_node_resources(input_request)

    # No resources to reserve
    if input_request_transform.get_nof_resources() == 0:
        return rs.ResourceList([])

    try:
        while timeout_handler.not_reached():
            # Get resources in the cluster
            all_node_resources = ts.get_node_resources(get_resources_in_cluster(k_server))
            available_node_resources = ts.get_available_resources(k_server, all_node_resources)

            for resource_space, matched_resources in _calculate_resource_space_from_request(
                input_request_transform, available_node_resources
            ):
                result = utils.reserve_space_configmap(
                    k_server=k_server,
                    space=resource_space,
                    orch_id=orch_id,
                    user_name=user_name,
                    timeout=int(timeout_handler.get_remaining_timeout()),
                )
                if result:
                    if matched_resources.reserve(
                        k_server,
                        orch_id,
                        user_name,
                        timeout_seconds=int(timeout_handler.get_remaining_timeout()),
                        num_of_retry=1,
                        num_seconds_per_retry=0,
                    ):
                        return matched_resources

            sleep(RESERVATION_NUM_SECONDS_BETWEEN_RETRIES)

        raise RuntimeError("No resources in the cluster matching the request")

    except TimeoutError as err:
        all_node_resources = ts.get_node_resources(get_resources_in_cluster(k_server))
        for resource_space, matched_resources in _calculate_resource_space_from_request(
            input_request_transform, all_node_resources
        ):
            logging.error(
                "Resource space %s is occupied by user %s: %s",
                resource_space,
                k_server.get_config_map(get_space_name(resource_space)).data.get("user_name", ""),
                " | ".join(
                    f"{possible_resource.model} ({possible_resource.node.name})"
                    for possible_resource in matched_resources.get_resources()
                ),
            )
        raise err


def _calculate_resource_space_from_request(
    input_request: rs.ResourceList, node_resources: rs.ResourceList
) -> Generator[Tuple[str, rs.ResourceList], None, None]:
    resource_space_groups = ts.group_by_resource_space(node_resources)

    # Shuffle resource space so we don't always try them in same order
    resource_space_keys = list(resource_space_groups.keys())
    shuffle(resource_space_keys)

    # Match resources in cluster with request
    for resource_space in resource_space_keys:
        resource_list = resource_space_groups[resource_space]
        matched_resources = ts.get_match_resources(input_request, resource_list)

        # Check if match is ok
        if matched_resources.get_nof_resources() == input_request.get_nof_resources():
            yield resource_space, matched_resources


def reserve_cluster_resources(
    k_server: Kubernetes, input_request: rs.ResourceList, orch_id: str, user_name: str, timeout_handler: TimeoutHandler
) -> rs.ResourceList:
    """
    Cluster reservation
    """

    # Get cluster resources in request
    input_request_transform = ts.get_cluster_resources(input_request)

    # No resources to reserve
    if input_request_transform.get_nof_resources() == 0:
        return rs.ResourceList([])

    possible_cluster_resources = rs.ResourceList([])
    try:
        while timeout_handler.not_reached():
            # Get resources in the cluster
            all_cluster_resources = ts.get_cluster_resources(get_resources_in_cluster(k_server))
            available_cluster_resources = ts.get_available_resources(k_server, all_cluster_resources)

            # Check if it's possible to reserve the resources (if compatible resources exist even reserved)
            possible_cluster_resources = ts.get_match_resources(input_request_transform, all_cluster_resources, False)
            if possible_cluster_resources.get_nof_resources() != input_request_transform.get_nof_resources():
                raise RuntimeError("No resources in the cluster matching the request")

            # Match resources in cluster with request
            matching_cluster_resources = ts.get_match_resources(input_request_transform, available_cluster_resources)
            if matching_cluster_resources.get_nof_resources() == input_request_transform.get_nof_resources():
                # Reserve resources
                if matching_cluster_resources.reserve(
                    k_server,
                    orch_id,
                    user_name,
                    timeout_seconds=int(timeout_handler.get_remaining_timeout()),
                    num_of_retry=1,
                    num_seconds_per_retry=0,
                ):
                    return matching_cluster_resources

            sleep(RESERVATION_NUM_SECONDS_BETWEEN_RETRIES)

        raise RuntimeError("No resources in the cluster matching the request")

    except TimeoutError as err:
        for possible_resource in possible_cluster_resources.get_resources():
            logging.error(
                "Resource %s is occupied by user %s.",
                possible_resource.get_full_name(),
                possible_resource.get_user_name(k_server),
            )
        raise err


def get_resources_in_cluster(k_server: Kubernetes) -> rs.ResourceList:
    """
    Get resources
    """
    resource_list = rs.get_resource_from_cluster_info(
        k_server.get_cluster_configuration(), k_server.get_retina_node_dict(False, False)
    )
    return resource_list
