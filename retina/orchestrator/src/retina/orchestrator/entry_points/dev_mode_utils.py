#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Dev mode utils
"""

import json
import logging
import os
import random
import re
import signal
import string
import sys
from typing import Dict, List, Optional, Tuple

import rich as rch
import yaml

from retina.orchestrator.const import RETINA_DEPLOY_LABEL_KEY
from retina.orchestrator.entry_points.utils import (
    get_error_level,
    print_table,
    print_table_resources,
    set_default_colored_logger,
)
from retina.orchestrator.orchestration_network import OrchestratorManager
from retina.orchestrator.retina_kubernetes import DEFAULT_NAMESPACE, Kubernetes, PodStatus
from retina.orchestrator.utils import get_retina_user

DEFAULT_TIMEOUT = 5 * 60
DEFAULT_DOCKER_IMAGE = "docker/desktop-kubernetes-pause:3.10"


def _signal_handler(*args, **kwargs):
    raise KeyboardInterrupt


def get_random_filename():
    """
    Get random filename
    """
    return f"/tmp/{get_random_name()}.yaml"


def get_random_name():
    """
    Get random name
    """
    login_username = get_retina_user()
    caracteres = string.ascii_lowercase + string.digits
    string_aleatorio = "".join(random.choice(caracteres) for _ in range(11))
    return f"{string_aleatorio}{login_username}"


def create_request(k_server: Kubernetes, node_name: str, docker_image: str, verbose: bool):
    """
    Create request
    """
    if node_name not in k_server.get_retina_node_dict(True, True):
        print(f"Node {node_name} not found.")
        sys.exit(1)

    node_compute_resources = None
    for cluster_node in k_server.get_cluster_configuration()["nodes"]:
        if cluster_node["name"] == node_name:
            node_compute_resources = cluster_node["compute-resources"]
            break
    else:
        print(f"Node {node_name} has no compute resources. Ask the administrator to add them.")
        sys.exit(1)

    node_huge_pages_1gi = node_compute_resources.get("hugepages-1Gi", None)

    request_json: List[Dict] = [
        {
            "name": (re.sub("[^A-Za-z0-9]+", "", get_retina_user()) + "-" + re.sub("[^A-Za-z0-9]+", "", node_name))[
                :23
            ],
            "image": docker_image,
            "labels": [f"kubernetes.io/hostname={node_name}"],
            "host_network": "InternalIP",
            "requirements": {
                "cpu": {
                    "requests": "100%",
                    "limits": "100%",
                },
                "memory": {
                    "requests": "100%",
                    "limits": "100%",
                },
                "ephemeral-storage": {
                    "requests": "100%",
                    "limits": "100%",
                },
            },
        }
    ]

    if node_huge_pages_1gi:
        request_json[0]["requirements"]["hugepages-1Gi"] = {
            "requests": node_huge_pages_1gi,
            "limits": node_huge_pages_1gi,
        }

    if verbose:
        logging.info("Request: \n%s", json.dumps(request_json, indent=4))

    request_yaml = yaml.dump(request_json)

    output_filename = get_random_filename()
    try:
        os.remove(output_filename)
    except FileNotFoundError:
        pass

    with open(output_filename, "w", encoding="UTF-8") as f:
        f.write(request_yaml)

    return output_filename


def print_id(orch_id):
    """
    Print ID
    """
    rch.print(f"\n[bold magenta]• Orchestration network ID: {orch_id}")


def print_cmd(result, node_name: str, has_ssh: bool):
    """
    Open cmd
    """
    if result:
        for res_inst in result:
            rch.print("\n[bold cyan]-> Connection")
            if has_ssh:
                rch.print(f"    [bold green]• SSH: ssh root@{res_inst.address} -p {res_inst.port_array[0]}")
                rch.print(
                    f"    [bold green]• scp: scp -P {res_inst.port_array[0]} ./myfile.txt root@{res_inst.address}:/home"
                )
            rch.print(f"    [bold green]• Using kubectl: kubectl cp /myfile.txt -n retina {res_inst.pod_name}:/home")
            rch.print(
                f"    [bold green]• kubectl: kubectl exec --stdin --tty {res_inst.pod_name} -n retina -- /bin/bash"
            )
            rch.print("\n[bold cyan]-> How to delete the dev environment?:")
            rch.print(f"    [bold green]• retina release {node_name}\n")


def _get_reserved_info_from_node(k_server: Kubernetes, node_name: str) -> Optional[Tuple[str, str]]:
    retina_pods_in_node = k_server.search_pods(
        status_array=[PodStatus.RUNNING.value], node_name_array=[node_name], namespace_array=[DEFAULT_NAMESPACE]
    )
    dev_mode_pod_array = [
        pod
        for pod in retina_pods_in_node
        if pod.metadata.labels[RETINA_DEPLOY_LABEL_KEY] != pod.metadata.name
        or ("dev_mode" in pod.metadata.annotations and pod.metadata.annotations["dev_mode"] == "true")
    ]
    for pod in dev_mode_pod_array:
        user_name = (
            pod.metadata.annotations["user_name"]
            if pod.metadata.annotations and "user_name" in pod.metadata.annotations
            else None
        )
        orch_id = (
            pod.metadata.annotations["orch_id"]
            if pod.metadata.annotations and "orch_id" in pod.metadata.annotations
            else None
        )
        if user_name is not None and orch_id is not None:
            return user_name, orch_id
    return None


def release_node(k_server: Kubernetes, node_name: str):
    """
    Release node
    """

    reserved_data = _get_reserved_info_from_node(k_server, node_name)
    if reserved_data is None:
        return
    user_name, orch_id = reserved_data
    logging.info("💻 Releasing from user %s", user_name)
    orch_manager = OrchestratorManager()
    orch_manager.delete_orchestration_network(orch_id)


def delete_orchestration_network_by_username(username: str, is_incluster: bool = False):
    """
    Delete orchestration network by username

    Args:
        username: The username to delete orchestration networks for
        is_incluster: Whether to use in-cluster Kubernetes config
    """
    orch_manager = OrchestratorManager(is_incluster=is_incluster)
    orch_manager.delete_orchestration_network_by_username(username, False)


# pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments
def reserve_node(k_server: Kubernetes, node_name: str, username: str, verbose: bool, image: str, loglevel: str) -> bool:
    """
    Reserve node
    """
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGTSTP, _signal_handler)
    signal.signal(signal.SIGQUIT, _signal_handler)

    log_level = get_error_level(loglevel)

    set_default_colored_logger(log_level)

    is_ok = False

    input_request = create_request(k_server, node_name, image, verbose)

    reserved_data = _get_reserved_info_from_node(k_server, node_name)
    if reserved_data is not None:
        reserved_user_name, _ = reserved_data
        logging.error("❌ Node %s is already reserved by %s.", node_name, reserved_user_name)
        return False

    pods_per_node = k_server.search_pods(status_array=[PodStatus.RUNNING.value], node_name_array=[node_name])
    if pods_per_node:
        msg_pods = f"Pods already running in node {node_name}:\n"
        for pod in pods_per_node:
            msg_pods += f"     Pod: {pod.metadata.name}, Namespace: {pod.metadata.namespace}\n"
        logging.warning(msg_pods)

    try:
        orch_manager = OrchestratorManager()
        orch_id, result, _ = orch_manager.create_infrastructure(
            request_path=input_request,
            user_name=username,
            timeout=DEFAULT_TIMEOUT,
            print_info=False,
            dev_mode=True,
            not_finite_execution=not image == DEFAULT_DOCKER_IMAGE,
        )

        is_ok = True

        if verbose:
            print_id(orch_id)
            print_table(result)
            print_table_resources(result)
            print_cmd(result, node_name, image == DEFAULT_DOCKER_IMAGE)
    finally:
        try:
            os.remove(input_request)
            # pylint: disable=R0801
            if not is_ok:
                logging.getLogger().setLevel(logging.INFO)
                orch_manager.delete_orchestration_network()
        except Exception as err:  # pylint: disable=broad-exception-caught
            logging.exception(err)
    return is_ok
