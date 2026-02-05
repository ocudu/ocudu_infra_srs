#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Transformations for the reservation module
"""

import copy
import itertools
from random import shuffle
from typing import Dict, List

import retina.orchestrator.reservation.resources as rs
from retina.orchestrator.retina_kubernetes import Kubernetes


def get_cluster_resources(resource_list: rs.ResourceList) -> rs.ResourceList:
    """
    Get cluster resources
    """
    new_list = [r for r in resource_list.get_resources() if r.is_cluster_resource()]
    return rs.ResourceList(new_list)


def get_node_resources(resource_list: rs.ResourceList) -> rs.ResourceList:
    """
    Get node resources
    """
    new_list = [r for r in resource_list.get_resources() if not r.is_cluster_resource()]
    return rs.ResourceList(new_list)


def get_available_resources(kubernetes: Kubernetes, resource_list: rs.ResourceList) -> rs.ResourceList:
    """
    Get avaiable resources
    """
    new_list = [r for r in resource_list.get_resources() if r.is_available(kubernetes)]
    return rs.ResourceList(new_list)


def get_resources_by_id(resource_list: rs.ResourceList, id_def: str) -> rs.ResourceList:
    """
    Get resources by id
    """
    new_list = [r for r in resource_list.get_resources() if r.id_name == id_def]
    return rs.ResourceList(new_list)


def get_match_resources(
    input_resource_list: rs.ResourceList,
    complete_resource_list: rs.ResourceList,
    enable_set_id: bool = True,
) -> rs.ResourceList:
    """
    Get match resources
    """

    # For each resource_input (in input_resource_list) search list of all resources
    # that matches for it
    matching_resource_dict: Dict[int, List] = {}
    # pylint: disable=too-many-nested-blocks
    for index, resource_input in enumerate(input_resource_list.get_resources()):
        matching_resource_dict[index] = []  # List of resources matching this resource_input
        for resource_complete in complete_resource_list.get_resources():
            if resource_input == resource_complete and resource_complete.get_id() is None:
                if resource_input.is_cluster_resource() or resource_input.node is None:
                    matching_resource_dict[index].append(resource_complete)
                else:
                    configured_taints = tuple(sorted(resource_input.node.get_taint_list_as_string()))
                    reserved_taints = tuple(sorted(resource_complete.node.get_taint_list_as_string()))
                    if (
                        not configured_taints
                        or (configured_taints == reserved_taints or configured_taints in reserved_taints)
                    ) and resource_complete.node.check_label_list(resource_input.node.label_list):
                        if resource_input.capacity == 0:
                            resource_complete = copy.deepcopy(resource_complete)
                            resource_complete.capacity = -index
                        matching_resource_dict[index].append(resource_complete)

    # Create all combinations of matching resources, filtering the ones with duplicated items
    combinations = list(
        filter(
            lambda array: len(set(array)) == (index + 1),
            itertools.product(*matching_resource_dict.values()),
        )
    )
    if combinations:
        # If there is at least one valid combination, we shuffle them and pick one
        shuffle(combinations)
        result = combinations[0]

        # Set the ID for the selected match resources
        for index, resource_input in enumerate(input_resource_list.get_resources()):
            if enable_set_id:
                result[index].set_id(resource_input.id_name)

        return rs.ResourceList(result)

    return rs.ResourceList([])


def group_by_resource_space(input_resource_list: rs.ResourceList) -> Dict[int, rs.ResourceList]:
    """
    Group by space
    """
    rs_groups: Dict[int, rs.ResourceList] = {}

    for cls_inst in input_resource_list.get_resources():
        space = cls_inst.space
        if space in rs_groups:
            rs_groups[space].add_resource(cls_inst)
        else:
            rs_groups[space] = rs.ResourceList([cls_inst])
    return rs_groups
