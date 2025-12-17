#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Contains a basic Kubernetes manager class that encapsulates logic for
creating, deleting and managing Kubernetes resources such as config maps and pods.
"""

import contextlib
import json
import logging
import os
import subprocess
from abc import ABCMeta
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from kubernetes.client import (
    AppsV1Api,
    Configuration,
    CoreV1Api,
    V1ConfigMap,
    V1ConfigMapList,
    V1Deployment,
    V1DeploymentList,
    V1Node,
    V1NodeList,
    V1Pod,
    V1PodList,
    V1Service,
    V1ServiceList,
)
from kubernetes.client.exceptions import ApiException
from kubernetes.config import load_incluster_config, load_kube_config
from kubernetes.config.config_exception import ConfigException
from kubernetes.config.incluster_config import SERVICE_HOST_ENV_NAME, SERVICE_PORT_ENV_NAME, SERVICE_TOKEN_FILENAME

import retina.orchestrator.const as cnt
from retina.orchestrator.utils import get_kubeconfig_extra_list, run_command, validate_manifest

KUBERNETES_SKIP_TAINT_ARRAY = (
    "node.kubernetes.io/not-ready",  # Node is not ready. NodeCondition Ready is "False".
    "node.kubernetes.io/unreachable",  # Node is unreachable from the node controller. NodeCondition Ready is "Unknown".
    "node.kubernetes.io/memory-pressure",  # Node has memory pressure.
    "node.kubernetes.io/disk-pressure",  # Node has disk pressure.
    "node.kubernetes.io/pid-pressure",  # Node has PID pressure.
    "node.kubernetes.io/network-unavailable",  # Node's network is unavailable.
    "node.kubernetes.io/unschedulable",  # Node is unschedulable.
)


class ErrorCode(Enum):
    """
    Kubernetes error code
    """

    OTHER = 2
    OK = 0
    NAME_DUPLICATED = 409
    UNPROCESSABLE_ENTITY = 422


class KubernetesManager(metaclass=ABCMeta):  # pylint: disable=too-few-public-methods
    """
    Kubernetes manager class that encapsulates logic for creating, deleting and managing
    resources such as config maps and pods.
    """

    ############################################################################
    # Init and status check
    ############################################################################

    def __init__(self, is_incluster=False):
        if is_incluster:
            try:
                load_incluster_config()
            except ConfigException as err:
                raise RuntimeError("Error loading in-cluster config") from err
        else:
            load_kube_config(context=os.getenv("KUBECONFIG_CONTEXT"))

        self._api_instance = CoreV1Api()
        self._api_app_instance = AppsV1Api()
        self._kubeconfig_path = ""

        is_alive = self._check_server_status()
        if is_alive:
            return
        logging.warning("Error loading default Kubeconfig")

        # Try to use extra kubeconfig
        extra_kubeconfig_list = get_kubeconfig_extra_list()
        for extra_kubeconfig in extra_kubeconfig_list:
            try:
                load_kube_config(config_file=extra_kubeconfig)
                self._api_instance = CoreV1Api()
                self._api_app_instance = AppsV1Api()
                self._kubeconfig_path = extra_kubeconfig
                is_alive = self._check_server_status()
                if is_alive:
                    logging.info("Using alternative kubeconfig: %s", extra_kubeconfig)
                    return
                logging.warning("Error loading kubeconfig: %s", extra_kubeconfig)
            except Exception:  # pylint: disable=broad-exception-caught
                logging.warning("Error loading kubeconfig: %s", extra_kubeconfig)

        msg = "Kubernetes server is down."
        raise RuntimeError(msg)

    @staticmethod
    def is_incluster():
        """
        Check if the current environment is a Kubernetes cluster
        """
        return (
            Configuration.get_default_copy().host
            == f"https://{os.getenv(SERVICE_HOST_ENV_NAME)}:{os.getenv(SERVICE_PORT_ENV_NAME)}"
            and os.path.exists(SERVICE_TOKEN_FILENAME)
        )

    def _check_server_status(self) -> bool:
        with contextlib.suppress(Exception):
            self._api_instance.get_api_resources(_request_timeout=cnt.KUBERNETES_REQUEST_TIMEOUT)
            return True
        return False

    def _get_error_code(self, error_number: int) -> ErrorCode:
        """
        Transform API number code to error code
        """
        return_code = ErrorCode.OTHER
        if error_number == ErrorCode.OK.value:
            return_code = ErrorCode.OK
        elif error_number == ErrorCode.NAME_DUPLICATED.value:
            return_code = ErrorCode.NAME_DUPLICATED
        return return_code

    ############################################################################
    # Create / Delete Kubernetes element
    ############################################################################

    def _create(self, f_create, manifest: Dict, namespace: str, async_mode=False) -> ErrorCode:
        """
        Create Kubernetes element

        :param f_create: function to create element
        :param manifest: element manifest
        :param namespace: namespace
        :return: result code
        """
        if not validate_manifest(manifest):
            logging.error("Invalid manifest: %s", json.dumps(manifest, indent=4))
            raise RuntimeError("Invalid manifest")

        return_code = self._get_error_code(0)
        try:
            f_create(
                body=manifest,
                namespace=namespace,
                async_req=async_mode,
                _request_timeout=cnt.KUBERNETES_REQUEST_TIMEOUT,
            )
        except ApiException as error_n:
            if error_n.status is None:
                return_code = ErrorCode.OTHER
            else:
                return_code = self._get_error_code(error_n.status)
        return return_code

    def _delete(self, f_delete, name: str, namespace: str, **kwargs) -> ErrorCode:
        """
        Delete Kubernetes element

        :param f_delete: function to delete element
        :param name: element name
        :param namespace: namespace
        :return: result code
        """
        try:
            f_delete(
                namespace=namespace,
                name=name,
                propagation_policy="Foreground",
                _request_timeout=cnt.KUBERNETES_REQUEST_TIMEOUT,
                **kwargs,
            )
        except ApiException as error_n:
            if error_n.status is None:
                return ErrorCode.OTHER
        return self._get_error_code(0)

    ############################################################################
    # Service
    ############################################################################

    def _create_service(self, manifest: Dict, namespace: str) -> ErrorCode:
        """
        Create service

        :param manifest: manifest
        :param namespace: resource label
        """
        return self._create(self._api_instance.create_namespaced_service, manifest, namespace)

    def _delete_service(self, name: str, namespace: str) -> ErrorCode:
        """
        Delete service

        :param name: service name
        :param namespace: resource label
        """
        return self._delete(self._api_instance.delete_namespaced_service, name, namespace)

    def _get_service_dict(self, namespace: str) -> Dict[str, V1Service]:
        """
        Get all the services in a namespace
        """
        service_dict = {}
        service_list: V1ServiceList = self._api_instance.list_namespaced_service(
            namespace, _request_timeout=cnt.KUBERNETES_REQUEST_TIMEOUT
        )
        for service in service_list.items:
            service_dict[service.metadata.name] = service
        return service_dict

    ############################################################################
    # Config Maps
    ############################################################################
    def _create_config_map(self, manifest: Dict, namespace: str) -> ErrorCode:
        """
        Create config map

        :param manifest: manifest
        :param namespace: resource label
        """
        return self._create(self._api_instance.create_namespaced_config_map, manifest, namespace)

    def _delete_config_map(self, name: str, namespace: str) -> ErrorCode:
        """
        Delete config map

        :param name: config map name
        :param namespace: resource label
        """
        return self._delete(self._api_instance.delete_namespaced_config_map, name, namespace)

    def _get_config_map_dict(self, namespace: str) -> Dict[str, V1ConfigMap]:
        """
        Get all the configmaps in a namespace
        """
        config_map_dict = {}
        config_map_list: V1ConfigMapList = self._api_instance.list_namespaced_config_map(
            namespace, _request_timeout=cnt.KUBERNETES_REQUEST_TIMEOUT
        )
        for config_map in config_map_list.items:
            config_map_dict[config_map.metadata.name] = config_map
        return config_map_dict

    ############################################################################
    # Pods
    ############################################################################

    def _get_pod_dict(self, namespace: str) -> Dict[str, V1Pod]:
        """
        Get all pods in the namespace
        """
        pod_dict = {}
        pod_list: V1PodList = self._api_instance.list_namespaced_pod(
            namespace=namespace, _request_timeout=cnt.KUBERNETES_REQUEST_TIMEOUT
        )
        for pod in pod_list.items:
            pod_dict[pod.metadata.name] = pod
        return pod_dict

    def copy_to_pod(self, local_folder: str, remote_folder: str, pod_name: str, namespace: str) -> str:
        """
        Copy local folder to Pod
        """
        extra_args = f"--kubeconfig={self._kubeconfig_path}" if self._kubeconfig_path else ""
        # Creates destination folder
        for _ in range(3):  # Retry up to 3 times
            with contextlib.suppress(subprocess.CalledProcessError):
                run_command(
                    f"kubectl {extra_args} exec {pod_name} -n {namespace} -- mkdir -p {Path(remote_folder).parent}"
                )
                break
        # Copies the file or dir
        result = run_command(
            f"kubectl {extra_args} cp --retries=-1 {local_folder} {namespace}/{pod_name}:{remote_folder}"
        )
        return result

    def _create_pod(self, manifest: Dict, namespace: str) -> ErrorCode:
        """
        Create Pod

        :param manifest: manifest
        :param namespace: resource label
        """
        return self._create(self._api_instance.create_namespaced_pod, manifest, namespace)

    def _delete_pod(self, name: str, namespace: str, grace_period_seconds: Optional[int]) -> ErrorCode:
        """
        Delete Pod

        :param name: pod name
        :param namespace: resource label
        """
        return self._delete(
            self._api_instance.delete_namespaced_pod, name, namespace, grace_period_seconds=grace_period_seconds
        )

    @staticmethod
    def _force_delete_pod(pod_name: str, namespace: str):
        """
        Force delete pod
        """
        with contextlib.suppress(subprocess.CalledProcessError):
            run_command(f"kubectl delete pod --force {pod_name} --namespace {namespace}")

    def get_pod_event(self, pod: V1Pod) -> str:
        """
        Get pod event message
        """
        msg = ""
        if pod.status.conditions:
            msg += pod.status.conditions[-1].type
            if pod.status.conditions[-1].message is not None:
                msg += f" ({pod.status.conditions[-1].message})"
            if pod.status.container_statuses:
                last_container_status = pod.status.container_statuses[-1]
                if last_container_status.state.waiting:
                    msg += f" | {last_container_status.state.waiting.reason}"
        if pod.status.message:
            if msg:
                msg += " | "
            msg += pod.status.message
        return msg if msg else "No events found for this pod"

    ############################################################################
    # Deployment
    ############################################################################
    def _get_deployment_dict(self, namespace: str) -> Dict[str, V1Deployment]:
        """
        Get all deployments in the namespace
        """
        deployment_dict = {}
        deployment_list: V1DeploymentList = self._api_app_instance.list_namespaced_deployment(
            namespace=namespace, _request_timeout=cnt.KUBERNETES_REQUEST_TIMEOUT
        )
        for deployment in deployment_list.items:
            deployment_dict[deployment.metadata.name] = deployment
        return deployment_dict

    def _create_deployment(self, manifest: Dict, namespace: str) -> ErrorCode:
        """
        Create Deployment

        :param manifest: manifest
        :param namespace: resource label
        """
        return self._create(self._api_app_instance.create_namespaced_deployment, manifest, namespace)

    def _delete_deployment(self, name: str, namespace: str, grace_period_seconds: Optional[int]) -> ErrorCode:
        """
        Delete Deployment

        :param name: deployment name
        :param namespace: resource label
        """
        return self._delete(
            self._api_app_instance.delete_namespaced_deployment,
            name,
            namespace,
            grace_period_seconds=grace_period_seconds,
        )

    @staticmethod
    def _force_delete_deployment(deployment_name: str, namespace: str):
        """
        Force delete deployment
        """
        with contextlib.suppress(subprocess.CalledProcessError):
            run_command(f"kubectl delete deployment --force {deployment_name} --namespace {namespace}")

    ############################################################################
    # Node
    ############################################################################

    def _get_node_dict(self, skip_not_available: bool) -> Dict[str, V1Node]:
        """
        Get all nodes in the cluster
        """
        node_dict = {}
        node_list: V1NodeList = self._api_instance.list_node(_request_timeout=cnt.KUBERNETES_REQUEST_TIMEOUT)
        for node in node_list.items:
            # Filter not available nodes
            if skip_not_available:
                for taint in node.spec.taints if node.spec.taints else []:
                    if taint.key in KUBERNETES_SKIP_TAINT_ARRAY:
                        continue  # Skip this node

            node_dict[node.metadata.name] = node
        return node_dict

    def _create_label_in_node(self, node_name: str, key: str, value: str):
        """
        Create label in node
        """
        run_command(f"kubectl label --overwrite nodes {node_name} {key}={value}")

    def _delete_label_in_node(self, node_name: str, key: str):
        """
        Remove node label
        """
        run_command(f"kubectl label nodes {node_name} {key}-")
