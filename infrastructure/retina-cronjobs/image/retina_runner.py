#!/usr/bin/env python3
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Entrypoint
"""

import argparse
import base64
import json
import logging
import os
from typing import List, Union

import gitlab
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from retina.orchestrator.kubernetes import KUBERNETES_SKIP_TAINT_ARRAY
from retina.orchestrator.retina_kubernetes import Kubernetes

RETINA_TAG = "paused-by-retina"

RUNNERS_NAMESPACE = "retina"
RUNNERS_CONFIGMAP_KEY = "runners"


# pylint: disable=too-many-arguments,too-many-positional-arguments
def change_runner_status(runner_id: int, gitlab_token: str, paused: bool, node: str):
    """
    Change the status of a runner
    """
    try:
        gl = gitlab.Gitlab("https://gitlab.com", private_token=gitlab_token)
        runner = gl.runners.get(runner_id)

        runner_tags = list(runner.tag_list)

        if runner.online and runner.paused != paused:
            # runner is paused, runner was not paused by retina, so we can't activate it
            if runner.paused and RETINA_TAG not in runner_tags:
                return

            runner.paused = paused

            # if runner is paused, add tag to runner
            if paused:
                runner.tag_list.append(RETINA_TAG)
            # if runner is enabled, remove tag from runner
            else:
                index = runner.tag_list.index(RETINA_TAG)
                if index >= 0:
                    runner.tag_list.pop(index)
            runner.save()

            logging.info("Runner %s in node `%s` is now %s", runner_id, node, "paused" if paused else "enabled")

    # pylint: disable=broad-exception-caught
    except Exception as error:
        logging.error("Error changing runner %s status: %s", runner_id, error)


def get_runner_list(k_server: Kubernetes):
    """
    Get the list of all runners in the cluster and the list of runners in each node
    """
    cluster_config = k_server.get_cluster_configuration()
    node_list = cluster_config["nodes"]

    runners_by_node = _load_runners_by_node_from_configmap()
    runner_list_by_node = {}
    all_runner_list = []
    for node in node_list:
        node_name = node["name"]
        runner_list = runners_by_node.get(node_name, [])
        runner_list_by_node[node_name] = runner_list
        all_runner_list.extend(runner_list)
    return all_runner_list, runner_list_by_node


def _load_runners_by_node_from_configmap():
    cm_name = os.getenv("RETINA_RUNNERS_CONFIGMAP", "")
    if not cm_name:
        raise RuntimeError("Missing env RETINA_RUNNERS_CONFIGMAP (expected ConfigMap name in namespace 'retina').")

    # runner-manager runs in-cluster; we keep kubeconfig fallback for local debugging.
    try:
        k8s_config.load_incluster_config()
    except Exception:  # pylint: disable=broad-exception-caught
        k8s_config.load_kube_config(context=os.getenv("KUBECONFIG_CONTEXT"))

    v1 = k8s_client.CoreV1Api()
    cm = v1.read_namespaced_config_map(cm_name, RUNNERS_NAMESPACE)
    if not cm.data or RUNNERS_CONFIGMAP_KEY not in cm.data or not cm.data[RUNNERS_CONFIGMAP_KEY]:
        raise RuntimeError(f"ConfigMap '{cm_name}' is missing data.{RUNNERS_CONFIGMAP_KEY} in namespace '{RUNNERS_NAMESPACE}'.")

    try:
        decoded = base64.b64decode(cm.data[RUNNERS_CONFIGMAP_KEY].encode("ascii")).decode("ascii")
        runners_by_node = json.loads(decoded)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise RuntimeError(f"Failed to decode runners from ConfigMap '{cm_name}'") from exc

    if not isinstance(runners_by_node, dict) or not runners_by_node:
        raise RuntimeError(f"ConfigMap '{cm_name}' contains empty/invalid runners map.")

    return runners_by_node


def get_node_of_runner(k_server: Kubernetes, runner_id: int):
    """
    Get the node of a runner
    """
    _, runner_list_by_node = get_runner_list(k_server)
    for node, runners in runner_list_by_node.items():
        for runner in runners:
            if runner["id"] == runner_id:
                return node
    return None


def get_nodes_to_block(k_server: Kubernetes):
    """
    Get the list of nodes that have the dev_mode annotation set to true
    """
    nodes_to_block = []
    all_pods_in_retina = k_server.search_pods(namespace_array=["retina"])
    for pod in all_pods_in_retina:
        try:
            node_name_to_block = pod.spec.node_name if pod.spec.node_name else get_node_name_select(pod)
            if node_name_to_block:
                nodes_to_block.append(node_name_to_block)
        except AttributeError:
            node_name_to_block = get_node_name_select(pod)
            if node_name_to_block:
                nodes_to_block.append(node_name_to_block)

    for node_name, node in k_server.get_retina_node_dict(only_retina_labels=False, skip_not_available=False).items():
        for taint in node.taint_list:
            if taint.key in KUBERNETES_SKIP_TAINT_ARRAY:
                nodes_to_block.append(node_name)

    node_to_block_not_repeat = list(set(nodes_to_block))

    logging.info("Nodes to block: %s", node_to_block_not_repeat)

    return node_to_block_not_repeat


def get_node_name_select(pod) -> Union[str, None]:
    """
    Get the node name from the pod using the node selector
    """
    annotations = pod.metadata.annotations
    if "dev_mode" in annotations and annotations["dev_mode"] == "true":
        selector_terms_list = (
            pod.spec.affinity.node_affinity.required_during_scheduling_ignored_during_execution.node_selector_terms
        )
        for term in selector_terms_list:
            for selector in term.match_expressions:
                if selector.key == "kubernetes.io/hostname":
                    return str(selector.values[0])
    return None


def get_runner_to_disable_by_time(runner_list: List, disable_mode: str):
    """
    Get the list of runners to disable based on the time
    """
    if not disable_mode:
        return []

    runners_to_disable = []
    for runner in runner_list:
        if disable_mode.lower() in runner.get("disable_when", []):
            runners_to_disable.append(runner["id"])
    if runners_to_disable:
        logging.info("Runners to disable by time: %s", runners_to_disable)
    return runners_to_disable


def get_runners_to_disable_enable(k_server: Kubernetes, disable_mode: str):
    """
    Get the list of runners to disable and enable based on the nodes to block
    """
    all_runner_list, runner_list_by_node = get_runner_list(k_server)
    nodes_to_block = get_nodes_to_block(k_server)

    runners_to_disable = []
    for node in nodes_to_block:
        if node in runner_list_by_node:
            runners_to_disable.extend(runner_list_by_node[node])

    all_runner_id_list = [runner["id"] for runner in all_runner_list]
    runners_to_disable_id_list = [runner["id"] for runner in runners_to_disable]

    runners_to_disable_id_list.extend(get_runner_to_disable_by_time(all_runner_list, disable_mode))

    runners_to_enable = list(set(all_runner_id_list) - set(runners_to_disable_id_list))
    runners_to_disable_id_list_clean = list(set(runners_to_disable_id_list))

    logging.info("Runners to disable: %s", runners_to_disable_id_list_clean)
    logging.info("Runners to enable: %s", runners_to_enable)

    return runners_to_disable_id_list_clean, runners_to_enable


def main():
    """
    Main function
    """
    logging.basicConfig(
        format="%(asctime)s \x1b[32;20m[%(levelname)s]\x1b[0m %(message)s",
        level=logging.INFO,
    )

    parser = argparse.ArgumentParser(description="Enable disable Gitlab runners.")
    parser.add_argument("--gitlab-token", type=str, required=False, help="Gitlab token")
    parser.add_argument("--incluster", action="store_true", help="Running inside the cluster")
    parser.add_argument(
        "--disable-mode",
        type=str,
        default="",
        help="Mode to disable runners. Options: nightly, weekly...",
    )

    args = parser.parse_args()

    incluster = args.incluster
    gitlab_token = args.gitlab_token or os.getenv("GITLAB_TOKEN")
    disable_mode = args.disable_mode

    k_server = Kubernetes(is_incluster=incluster)
    runners_to_disable, runners_to_enable = get_runners_to_disable_enable(k_server, disable_mode)

    for runner_id in runners_to_enable:
        change_runner_status(
            runner_id,
            gitlab_token,
            False,
            get_node_of_runner(k_server, runner_id),
        )

    for runner_id in runners_to_disable:
        change_runner_status(
            runner_id,
            gitlab_token,
            True,
            get_node_of_runner(k_server, runner_id),
        )


if __name__ == "__main__":
    main()

