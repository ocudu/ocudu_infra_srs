#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Kubernetes manager
"""

import base64
import concurrent.futures
import ipaddress
import json
import logging
import re
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from kubernetes import watch
from kubernetes.client import V1ConfigMap, V1Deployment, V1Pod, V1PodSpec, V1PodStatus, V1Service

from retina.orchestrator import const
from retina.orchestrator.configs import ConfigmapConfig, PodConfig
from retina.orchestrator.const import (
    CLUSTER_CONFIGURATION_CONFIGMAP_NAME,
    LABEL,
    PORT_SERVICE_NAME,
    RETINA_DEPLOY_LABEL_KEY,
    SERVICE_LOADBALANCER,
    SERVICE_NODEPORT,
    TERMINATION_GRACE_PERIOD_SECONDS,
)
from retina.orchestrator.elements import LabelDefinition, Node, TaintDefinition
from retina.orchestrator.kubernetes import ErrorCode, KubernetesManager
from retina.orchestrator.requirement import RequirementDefinition, RETINA_PREFIX
from retina.orchestrator.timeout_handler import TimeoutHandler

ALTERNATIVE_IP = "retina.srs.io/secondary-ip"


class PodStatus(Enum):
    """
    Pod status
    """

    PENDING = "pending"
    ERRORIMAGEPULL = "ErrImagePull"
    CRASHLOOPBACKOFF = "CrashLoopBackOff"
    INVALIDIMAGENAME = "InvalidImageName"
    RUNNING = "running"
    FAILED = "failed"
    ERROR = "error"


class ConnectionPath(Enum):
    """
    Connection path
    """

    USB = "/dev/bus/usb"
    PCI_SYS_BUS = "/sys/bus/pci"
    PCI_SYS_MODULE = "/sys/module"
    RUN = "/run"


class ConnectionMode(Enum):
    """
    Connection mode
    """

    USB = "usb"
    NETWORK = "network"


DEFAULT_NAMESPACE = "retina"


class Kubernetes(KubernetesManager):
    """
    Kubernetes manager
    """

    ############################################################################
    # Services
    ############################################################################
    def create_retina_service(self, config: Dict, namespace: str = DEFAULT_NAMESPACE):
        """
        Create service

        :param config: config
        :param namespace: resource label
        :return result
        """

        manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": config["name"]},
            "spec": {
                "type": config["type"],
                "ports": config["ports"],
                "selector": {"app": config["selector"]},
            },
        }
        return self._create_service(manifest, namespace)

    def get_load_balancer_service(self, namespace: str = DEFAULT_NAMESPACE) -> V1Service:
        """
        Get load balancer service
        """
        for service in self._get_service_dict(namespace).values():
            if service.metadata.name == PORT_SERVICE_NAME and service.spec.type == SERVICE_LOADBALANCER:
                return service
        return None

    def get_node_port_service(self, namespace: str = DEFAULT_NAMESPACE) -> V1Service:
        """
        Get node port service
        """
        for service in self._get_service_dict(namespace).values():
            if service.metadata.name == PORT_SERVICE_NAME and service.spec.type == SERVICE_NODEPORT:
                return service
        return None

    def get_load_balancer_ip(self) -> str:
        """
        Get load balancer information

        :return: info
        """
        ip_add = ""
        while True:
            service = self.get_load_balancer_service()
            if service is not None:
                try:
                    if service.status.load_balancer.ingress[0].ip is not None:
                        ip_add = service.status.load_balancer.ingress[0].ip
                    elif service.status.load_balancer.ingress[0].hostname is not None:
                        ip_add = service.status.load_balancer.ingress[0].hostname
                    return ip_add
                except:  # pylint: disable=bare-except
                    return ip_add

    ############################################################################
    # Config Maps
    ############################################################################

    def create_config_map(self, config: ConfigmapConfig, namespace: str = DEFAULT_NAMESPACE) -> ErrorCode:
        """
        Create config map

        :param config: config
        :param namespace: resource label
        :return result
        """

        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": config.name,
                "annotations": {
                    "orch_id": config.orch_id,
                    "user_name": config.user_name,
                },
            },
            "data": config.data,
        }
        if config.timeout is not None:
            manifest["metadata"]["annotations"]["timeout"] = str(config.timeout)

        return self._create_config_map(manifest, namespace)

    def delete_config_map_by_user_name(
        self, user_name: Optional[str], namespace: str, dryrun: bool, enable_regex: bool
    ) -> None:
        """
        Delete the configmaps by username. If username is None it will delete all the configmaps.
        """
        msg_init = "Deleting"
        if dryrun:
            msg_init = "To delete"

        # ConfigMap
        for config_map in self._get_config_map_dict(namespace).values():
            if "user_name" in config_map.data:
                is_here = False
                if user_name is None:
                    is_here = True
                elif enable_regex is False and user_name == config_map.data["user_name"]:
                    is_here = True
                elif enable_regex is True and re.match(user_name, config_map.data["user_name"]):
                    is_here = True

                if is_here:
                    msg = f"{msg_init} configMap: {config_map.metadata.name}"
                    logging.debug(msg)
                    if not dryrun:
                        self._delete_config_map(config_map.metadata.name, namespace)

    def delete_config_map(self, config_map_name: str, namespace: str = DEFAULT_NAMESPACE) -> None:
        """
        Delete config map by name
        """
        self._delete_config_map(config_map_name, namespace)

    def get_config_map(self, config_map_name: str, namespace: str = DEFAULT_NAMESPACE) -> V1ConfigMap:
        """
        Get config map by config map name

        :param config_map_name: name
        :param namespace: resource label
        :return: config map
        """
        return self._get_config_map_dict(namespace).get(config_map_name, V1ConfigMap())

    def config_map_exists(self, config_map_name: str, namespace: str = DEFAULT_NAMESPACE) -> bool:
        """
        Check if config map exist

        :param config map_name: name
        :param namespace: resource label
        :return: result
        """
        return self._get_config_map_dict(namespace).get(config_map_name, None) is not None

    def get_cluster_configuration(self, namespace: str = DEFAULT_NAMESPACE) -> Dict[str, Any]:
        """
        Get cluster info
        """
        info = {}
        config_map = self._get_config_map_dict(namespace).get(CLUSTER_CONFIGURATION_CONFIGMAP_NAME, None)
        if config_map is not None:
            config_map_data = config_map.data
            resource = json.loads(base64.b64decode(config_map_data["resource"].encode("ascii")).decode("ascii"))
            cluster_resource_list = json.loads(
                base64.b64decode(config_map_data["cluster_resource_list"].encode("ascii")).decode("ascii")
            )

            retina_node_dict = self.get_retina_node_dict(False, False)
            for i, value in enumerate(resource):
                n_name = value["name"]
                resource[i]["labels"] = retina_node_dict[n_name].label_list if n_name in retina_node_dict else []
                resource[i]["taints"] = retina_node_dict[n_name].taint_list if n_name in retina_node_dict else []

            info = {
                "networking-mode": config_map_data["networking-mode"],
                "dnsPolicy": config_map_data["dnsPolicy"],
                "update-time": config_map_data["update-time"],
                "version": config_map_data["version"],
                "nodes": resource,
                "cluster_resource_list": cluster_resource_list,
            }
        else:
            raise RuntimeError(f"Error getting cluster info: {CLUSTER_CONFIGURATION_CONFIGMAP_NAME}")
        return info

    def get_orch_id_list_by_username(
        self, user_name_expected: Optional[str], enable_regex: bool, namespace: str = DEFAULT_NAMESPACE
    ) -> List[str]:
        """
        Get orch id by username if username is None it will return all the orch_id
        """
        orch_id_list: List[str] = []
        annotation_list = [configmap.data for configmap in self._get_config_map_dict(namespace).values()]
        annotation_list.extend([pod.metadata.annotations for pod in self._get_pod_dict(namespace).values()])

        for annotation in annotation_list:
            if "orch_id" in annotation:
                orch_id = annotation["orch_id"]
                user_name = annotation["user_name"]
                is_here = False
                if user_name_expected is None:
                    is_here = True
                elif enable_regex is False and user_name_expected == user_name:
                    is_here = True
                elif enable_regex is True and re.match(user_name_expected, user_name):
                    is_here = True
                if orch_id not in orch_id_list and orch_id and is_here:
                    orch_id_list.append(annotation["orch_id"])

        return orch_id_list

    ############################################################################
    # Pods
    ############################################################################

    def search_pods(
        self,
        status_array: Optional[List[str]] = None,
        node_name_array: Optional[List[str]] = None,
        namespace_array: Optional[List[str]] = None,
    ) -> List[V1Pod]:
        """
        Get pods by filter
        """
        result = []
        if namespace_array is not None:
            for namespace in namespace_array:
                for pod in self._get_pod_dict(namespace=namespace).values():
                    # Filter by status
                    if status_array is not None:
                        pod_status: V1PodStatus = pod.status
                        if pod_status.phase.lower() not in status_array:
                            continue
                    # Filter by node name
                    if node_name_array is not None:
                        pod_spec: V1PodSpec = pod.spec
                        if pod_spec.node_name not in node_name_array:
                            continue
                    result.append(pod)
        return result

    # pylint: disable=too-many-branches, too-many-nested-blocks
    def create_pod_until_scheduled(self, config: PodConfig, namespace: str, timeout_handler: TimeoutHandler) -> V1Pod:
        """
        Create a pod until it is scheduled
        """
        last_pod = None
        try:
            while timeout_handler.not_reached():
                # Start watching before creating the pod so we can detect its creation
                w = watch.Watch()
                stream = w.stream(
                    self._api_instance.list_namespaced_pod,
                    namespace=namespace,
                    field_selector=f"metadata.name={config.name}",
                    timeout_seconds=int(timeout_handler.get_remaining_timeout()),
                    _request_timeout=(timeout_handler.get_remaining_timeout()),
                )
                # Create it
                self._create_retina_pod(config, namespace)
                for _ in stream:
                    w.stop()
                    break  # Pod created. Stop the watch

                while timeout_handler.not_reached():
                    _pod = self._get_pod_dict(namespace).get(config.name, None)
                    if _pod is None:
                        break  # Pod was removed. Try again creating it
                    if _pod.status.phase.lower() == PodStatus.RUNNING.value:
                        return _pod
                    if _pod.status.phase.lower() == PodStatus.FAILED.value:
                        # Pod not scheduled
                        last_pod = _pod
                        if _pod.status.container_statuses is None:
                            self._delete_pod(config.name, namespace, None)
                            # Wait until the pod is removed
                            while timeout_handler.not_reached():
                                if config.name not in self._get_pod_dict(namespace):
                                    break
                            break  # Try again creating the pod
                    # Pod scheduled but container failed
                    self._validate_containers_from_pod(_pod, config)
                    # Pod pending
                    if _pod.status.phase.lower() == PodStatus.PENDING.value:
                        last_pod = _pod
                    time.sleep(0.1)

        except TimeoutError:
            msg = f"[{config.name}] Timeout reached while creating the pod"
            if last_pod is not None:
                msg += self._get_failed_pod_msg(last_pod, config, namespace)
            logging.error(msg)

        raise RuntimeError(f"Error creating the pod for {config.name}")

    @staticmethod
    def _validate_containers_from_pod(_pod: V1Pod, config: PodConfig):
        for cont in _pod.status.container_statuses if _pod.status.container_statuses else tuple():
            if cont.state.waiting.reason in (
                PodStatus.ERRORIMAGEPULL.value,
                PodStatus.CRASHLOOPBACKOFF.value,
            ):
                # Abort. Retrying won't fix it
                logging.error(
                    "[%s] is not available: %s",
                    config.name,
                    cont.state.waiting.reason,
                )
                raise RuntimeError(f"Error creating the pod for {config.name}")
            if cont.state.waiting.reason == PodStatus.INVALIDIMAGENAME.value:
                # Abort. Retrying won't fix it
                logging.error(
                    "[%s] references an invalid image: %s",
                    config.name,
                    cont.state.waiting.reason,
                )
                raise RuntimeError(f"Error creating the pod for {config.name}")

    def _get_failed_pod_msg(self, last_pod: V1Pod, config: PodConfig, namespace: str) -> str:
        msg = f"\n  💥 Status: {self.get_pod_event(last_pod)}"
        if config.node_name:
            msg += f"\n  💻 Scheduled in node: {config.node_name}"
            for pod in self.search_pods(
                status_array=[PodStatus.RUNNING.value],
                node_name_array=[config.node_name],
                namespace_array=[namespace],
            ):
                msg += (
                    f"\n     - User {pod.metadata.annotations['user_name']} " f"is running the pod {pod.metadata.name}"
                )
        else:
            msg += "\n  💻 Not scheduled in any node"
        return msg

    def get_pod_ip(self, pod_name: str) -> str:
        """
        Retry multiple times to get pod IP
        raises RuntimeError if pod IP is not available

        :param pod_name: pod name
        :return: IP
        """
        max_attempts = 30
        while max_attempts > 0:
            max_attempts -= 1
            pod = self._get_pod_dict(namespace=DEFAULT_NAMESPACE).get(pod_name, None)
            if pod is not None and pod.status.pod_ip is not None:
                return pod.status.pod_ip
            time.sleep(2)
        raise RuntimeError("Error getting pod IP")

    def _create_retina_pod(self, config: PodConfig, namespace: str) -> ErrorCode:
        """
        Create Pod

        :param config: config
        :param dev_mode: whether to enable development mode
        :param namespace: Kubernetes namespace
        :return: result code
        """

        manifest: Dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": config.name,
                "annotations": {
                    "orch_id": config.orch_id,
                    "user_name": config.user_name,
                },
                "labels": {
                    "app": LABEL,
                    RETINA_DEPLOY_LABEL_KEY: config.name,
                },
            },
            "spec": {"restartPolicy": "Never", **self._create_pod_spec(config, False)},
        }
        return self._create_pod(manifest, namespace)

    def _create_pod_spec(self, config: PodConfig, dev_mode: bool) -> Dict:
        """
        Create Pod specification

        :param config: config
        :param dev_mode: whether to enable development mode
        :return: Dict
        """
        volumes: List[Any] = []
        volume_mounts: List[Any] = []

        # Add resources configmaps
        for cm in config.resource_data_configmap_list:
            volumes.append({"name": cm, "configMap": {"name": cm}})
            volume_mounts.append(
                {
                    "name": cm,
                    "mountPath": f"/etc/retina/resources/{cm}.yml",
                    "readOnly": True,
                    "subPath": const.RESOURCE_DATA_FILE,
                }
            )

        # Enable coredump logging
        volumes.append(
            {
                "name": "coredump-volume",
                "hostPath": {"path": "/mnt/coredump"},
            }
        )
        volume_mounts.append({"name": "coredump-volume", "mountPath": "/tmp/coredump"})

        # Device with USB connection
        if config.enable_usb_connection:
            v_name = ConnectionPath.USB.value.replace("/", "-")[1::]
            v_path = ConnectionPath.USB.value
            volumes.append({"name": v_name, "hostPath": {"path": v_path}})
            volume_mounts.append({"name": v_name, "mountPath": v_path})

        # Device with PCI connection
        if config.enable_pci_connection:
            for path in (ConnectionPath.PCI_SYS_BUS, ConnectionPath.PCI_SYS_MODULE):
                v_name = path.value.replace("/", "-")[1::]
                v_path = path.value
                volumes.append({"name": v_name, "hostPath": {"path": v_path}})
                volume_mounts.append({"name": v_name, "mountPath": v_path})

        if dev_mode:
            for v_name, v_path, v_ro in [
                ("home-volume", "/home", False),
                ("sys-cpu", "/sys/devices/system/cpu", False),
                ("proc-cpuinfo", "/proc/cpuinfo", False),
                ("host-modules", "/lib/modules", True),
                ("host-dev", "/dev", False),
            ]:
                volumes.append({"name": v_name, "hostPath": {"path": v_path}})
                volume_mounts.append({"name": v_name, "mountPath": v_path, "readOnly": v_ro})

        # Base Pod manifest
        manifest: Dict[str, Any] = {
            "terminationGracePeriodSeconds": int(config.grace_period),
            "hostNetwork": bool(config.enable_network_connection),
            "dnsPolicy": config.dns_policy,
            "containers": [
                {
                    "name": "retina-app",
                    "image": config.image,
                    "securityContext": {
                        "capabilities": {"add": ["SYS_NICE", "NET_ADMIN", "IPC_LOCK", "SYS_ADMIN"]},
                        "privileged": config.privileged,
                    },
                    "ports": [
                        {"containerPort": p, "name": f"port-{p}"} for p in config.retina_ports + config.extra_ports
                    ],
                    "volumeMounts": volume_mounts,
                }
            ],
            "volumes": volumes,
            "priorityClassName": "retina-e2e-priority",
            "imagePullSecrets": [{"name": "registry-credentials"}],
        }

        # Loop container if needed
        if config.not_finite_execution:
            manifest["containers"][0].update(
                {
                    "command": ["/bin/bash", "-c", "--"],
                    "args": ["while true; do sleep 30; done;"],
                }
            )

        # Environment variables
        env_list = [
            {"name": "RETINA_IP", "valueFrom": {"fieldRef": {"fieldPath": "status.podIP"}}},
            {"name": "RETINA_NODE_IP", "valueFrom": {"fieldRef": {"fieldPath": "status.hostIP"}}},
        ]
        for req in config.environment:
            for k, v in req.items():
                env_list.append({"name": k, "value": v})
        if config.retina_ports:
            env_list.append({"name": "RETINA_PORTS", "value": " ".join(map(str, config.retina_ports))})
        if env_list:
            manifest["containers"][0]["env"] = env_list

        # Apply other settings
        self._set_requirements(manifest, config.request_list, volumes, volume_mounts)
        self._set_tolerations(manifest, config.taint_list)
        self._set_command(manifest, config.command)
        self._set_node_affinity(manifest, config.label_list)
        if config.node_name:
            manifest["nodeName"] = config.node_name

        return manifest

    def _set_command(self, manifest: Dict, command: Union[None, List[str]]):
        """
        Set command in manifest
        """
        if command:
            manifest["containers"][0].update({"command": command})

    def _set_tolerations(self, manifest: Dict, taint_list: List[TaintDefinition]):
        """
        Set tolerations to manifest
        """
        # Tolerations
        if len(taint_list) == 0:
            return

        toleration_list = []
        for taint_inst in taint_list:
            toleration_list.append(
                {"key": taint_inst.key, "operator": "Equal", "value": taint_inst.value, "effect": "NoSchedule"}
            )
        manifest.update({"tolerations": toleration_list})

    def _set_node_affinity(self, manifest: Dict, label_list: List[LabelDefinition]):
        """
        Set node affinity to manifest
        """
        # Node affinity
        if len(label_list) == 0:
            return

        affinity_list = []
        for label_inst in label_list:
            if not label_inst.reverse:
                affinity_list.append({"key": label_inst.name, "operator": "In", "values": [label_inst.value]})
            else:
                affinity_list.append({"key": label_inst.name, "operator": "DoesNotExist"})

        affinity = {
            "nodeAffinity": {
                "requiredDuringSchedulingIgnoredDuringExecution": {
                    "nodeSelectorTerms": [{"matchExpressions": affinity_list}]
                }
            }
        }

        manifest.update({"affinity": affinity})

    def _set_requirements(
        self, manifest: Dict, requirement_list: List[RequirementDefinition], volumes: List, volume_mounts: List
    ):
        """
        Set pod requirements
        """
        if len(requirement_list) == 0:
            return

        requests = {}
        limits = {}

        manifest["containers"][0].update({"resources": {}})
        is_hugepage = False
        for requirement_inst in requirement_list:
            if requirement_inst.name == "hugepages-1Gi":
                is_hugepage = True
            if requirement_inst.requests:
                requests.update({requirement_inst.name: requirement_inst.requests})
            if requirement_inst.limits:
                limits.update({requirement_inst.name: requirement_inst.limits})

        complete_req = {}
        if requests:
            complete_req.update({"requests": requests})
        if limits:
            complete_req.update({"limits": limits})

        manifest["containers"][0]["resources"].update(complete_req)

        if is_hugepage:
            volumes.append({"name": "hugepage-1gi", "emptyDir": {"medium": "HugePages-1Gi"}})
            volume_mounts.append({"name": "hugepage-1gi", "mountPath": "/hugepages-1Gi"})

    def _delete_pod_and_wait(self, pod: V1Pod, dryrun: bool):
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        grace_period = pod.spec.termination_grace_period_seconds

        if pod.status.phase.lower() != PodStatus.RUNNING.value:
            # Warn if pod is not in running state
            logging_function = logging.error if pod.status.phase.lower() == PodStatus.FAILED.value else logging.warning
            logging_function(
                "Deleting %s: was not running. Status %s. Latest event: %s",
                pod_name,
                pod.status.phase,
                self.get_pod_event(pod),
            )
        else:
            logging.info("Deleting %s: starting %s sec grace period", pod_name, grace_period)

        if not dryrun:
            self._delete_pod(pod_name, namespace, grace_period)
            timeout_handler = TimeoutHandler(timeout=grace_period + 5)

            try:
                w = watch.Watch()
                exit_code = None
                for event in w.stream(
                    func=self._api_instance.list_namespaced_pod,
                    namespace=namespace,
                    field_selector=f"metadata.name={pod_name}",
                    timeout_seconds=int(timeout_handler.get_remaining_timeout()),
                ):
                    if event["object"].status.container_statuses:
                        for cs in event["object"].status.container_statuses:
                            term = cs.state.terminated
                            if term:
                                if exit_code is None:
                                    exit_code = 0
                                exit_code = exit_code if exit_code != 0 else term.exit_code
                    if event["type"] == "DELETED":
                        logging_function = logging.error if exit_code != 0 else logging.info
                        logging_function("Deleting %s: Exit code: %s", pod_name, exit_code)
                        w.stop()
                        break

                # Wait until the pod is actually removed
                try:
                    while timeout_handler.not_reached():
                        if pod_name not in self._get_pod_dict(namespace):
                            logging.info("Deletion %s: Pod removed", pod_name)
                            break
                        time.sleep(0.1)
                except TimeoutError:
                    logging.warning("Deleting %s: not end in the grace period. Forcing a deletion", pod_name)
                    self._force_delete_pod(pod_name, namespace)

            except Exception as err:  # pylint: disable=broad-exception-caught
                logging.warning("Deleting %s: Error found %s. Forcing a deletion", pod_name, err)
                self._force_delete_pod(pod_name, namespace)

    ############################################################################
    # Deployments
    ############################################################################

    def create_deployment_until_pod_scheduled(self, config: PodConfig, namespace: str, timeout_handler) -> V1Pod:
        """
        Create a deployment until its pod is scheduled
        """
        last_pod = None
        try:
            self._create_retina_deployment(config, namespace)
            while timeout_handler.not_reached():
                for _pod in self._get_pod_dict(namespace).values():
                    if _pod.metadata.labels.get(RETINA_DEPLOY_LABEL_KEY, "") == config.name:
                        # Found pod from our deployment
                        if _pod.status.phase.lower() == PodStatus.RUNNING.value:
                            return _pod
                        if _pod.status.phase.lower() == PodStatus.FAILED.value:
                            continue  # Pod not scheduled yet
                        # Pod scheduled but container failed
                        self._validate_containers_from_pod(_pod, config)
                        # Pod pending
                        if _pod.status.phase.lower() == PodStatus.PENDING.value:
                            last_pod = _pod
                        time.sleep(0.1)
        except TimeoutError:
            msg = f"[{config.name}] Timeout reached while creating the deployment"
            if last_pod is not None:
                msg += self._get_failed_pod_msg(last_pod, config, namespace)
            logging.error(msg)

        raise RuntimeError(f"Error creating the deployment for {config.name}")

    def _create_retina_deployment(self, config: PodConfig, namespace: str) -> ErrorCode:
        """
        Create Deployment

        :param config: config
        :param namespace: Kubernetes namespace
        :return: result code
        """
        manifest: Dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": config.name,
                "annotations": {
                    "orch_id": config.orch_id,
                    "user_name": config.user_name,
                },
                "labels": {
                    "app": LABEL,
                    RETINA_DEPLOY_LABEL_KEY: config.name,
                },
            },
            "spec": {
                "selector": {"matchLabels": {"app": LABEL}},
                "replicas": 1,
                "template": {
                    "metadata": {
                        "labels": {"app": LABEL, RETINA_DEPLOY_LABEL_KEY: config.name},
                        "annotations": {
                            "orch_id": config.orch_id,
                            "user_name": config.user_name,
                        },
                    },
                    "spec": self._create_pod_spec(config, True),
                },
            },
        }
        return self._create_deployment(manifest, namespace)

    def _delete_deployment_and_wait(self, deployment: V1Deployment, dryrun: bool):
        deployment_name = deployment.metadata.name
        namespace = deployment.metadata.namespace
        grace_period = TERMINATION_GRACE_PERIOD_SECONDS

        # Search for latest pod
        _last_pod = None
        for _pod in self._get_pod_dict(namespace).values():
            if _pod.metadata.labels.get(RETINA_DEPLOY_LABEL_KEY, "") == deployment_name:
                grace_period = max(grace_period, _pod.spec.termination_grace_period_seconds)
                if _last_pod is None or _pod.metadata.creation_timestamp > _last_pod.metadata.creation_timestamp:
                    _last_pod = _pod

        if _last_pod is None:
            logging.warning("Deleting %s: No pod found", deployment_name)
        elif _last_pod.status.phase.lower() != PodStatus.RUNNING.value:
            # Warn if pod is not in running state
            logging_function = (
                logging.error if _last_pod.status.phase.lower() == PodStatus.FAILED.value else logging.warning
            )
            logging_function(
                "Deleting %s: was not running. Status %s. Latest event: %s",
                deployment_name,
                _last_pod.status.phase,
                self.get_pod_event(_last_pod),
            )

        logging.info("Deleting %s", deployment_name)
        if not dryrun:
            self._delete_deployment(deployment_name, namespace, grace_period)
            # Don't care about exit code in deployments

            timeout_handler = TimeoutHandler(timeout=grace_period + 5)
            try:
                try:
                    while timeout_handler.not_reached():
                        if deployment_name not in self._get_deployment_dict(namespace):
                            logging.info("Deletion %s: Deployment removed", deployment_name)
                            break
                        time.sleep(0.1)
                except TimeoutError:
                    logging.warning("Deleting %s: not end in the grace period. Forcing a deletion", deployment_name)
                    self._force_delete_deployment(deployment_name, namespace)
            except Exception as err:  # pylint: disable=broad-exception-caught
                logging.warning("Deleting %s: Error found %s. Forcing a deletion", deployment_name, err)
                self._force_delete_deployment(deployment_name, namespace)

    ############################################################################
    # Nodes
    ############################################################################
    def get_retina_node_dict(self, only_retina_labels: bool, skip_not_available: bool) -> Dict[str, Node]:
        """
        Get node list with Retina info
        """
        retina_node_dict: Dict[str, Node] = {}
        for node_name, node in self._get_node_dict(skip_not_available).items():
            # Get label list
            label_list: List[LabelDefinition] = []
            for key, value in node.metadata.labels.items():
                if not only_retina_labels or key.startswith(RETINA_PREFIX):
                    label_list.append(LabelDefinition(key, value))

            # Get taints
            taint_list = node.spec.taints
            taint_key_list: List[str] = []
            if taint_list:
                for taint_inst in taint_list:
                    taint_key_list.append(
                        TaintDefinition(
                            key=taint_inst.key,
                            value=taint_inst.value,
                            effect=taint_inst.effect,
                        )
                    )
            retina_node_dict[node_name] = Node(
                name=node.metadata.name,
                architecture=node.status.node_info.architecture,
                os_image=node.status.node_info.os_image,
                kernel_version=node.status.node_info.kernel_version,
                label_list=label_list,
                taint_list=taint_key_list,
                ip_address=node.status.addresses[0].address,
                allocatable_cpu=(
                    float(node.status.allocatable["cpu"][:-1]) / 1000
                    if node.status.allocatable["cpu"].endswith("m")
                    else int(node.status.allocatable["cpu"])
                ),
                allocatable_memory=node.status.allocatable["memory"],
                allocatable_storage=node.status.allocatable["ephemeral-storage"],
            )
        return retina_node_dict

    def get_node_ip_dict(self, node_name: str) -> Dict[str, str]:
        """
        Get node port IP

        :return: info
        """
        ip_dict = {}
        node = self._get_node_dict(False).get(node_name, None)
        for addr_dict in node.status.addresses:
            try:
                ipaddress.ip_address(addr_dict.address)
                ip_dict[addr_dict.type] = addr_dict.address
            except ValueError:
                pass
        if ALTERNATIVE_IP in node.metadata.annotations:
            ip_dict[ALTERNATIVE_IP] = node.metadata.annotations[ALTERNATIVE_IP]

        return ip_dict

    def get_all_resources(self, label_init: str) -> List[Dict[str, Any]]:
        """
        Get all the resources starting by label_init

        :param label_init: init label
        :return: resource list
        """

        resource_list = []
        for node in self._get_node_dict(False).values():
            node_resources = node.status.allocatable
            node_resources_label = node_resources.keys()
            for resource in node_resources_label:
                if resource.startswith(label_init):
                    allocatable = int(node_resources[resource])
                    if allocatable > 0:
                        r_i = {
                            "node_name": node.metadata.name,
                            "name": resource,
                            "allocatable": node_resources[resource],
                            "capacity": node.status.capacity[resource],
                        }
                        resource_list.append(r_i)
        return resource_list

    ############################################################################
    # All
    ############################################################################

    def delete_all_by_orchid(self, orchid: str, namespace: str, dryrun: bool):
        """
        Get all configmap in namespace by orchid
        """
        # Deployments
        futures = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for deployment in self._get_deployment_dict(namespace).values():
                if (
                    deployment.metadata.annotations
                    and "orch_id" in deployment.metadata.annotations
                    and deployment.metadata.annotations["orch_id"] == orchid
                ):
                    futures.append(executor.submit(self._delete_deployment_and_wait, deployment, dryrun))
        concurrent.futures.wait(futures)
        logging.info("Deletion completed for deployments")

        # Pods
        futures = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for pod in self._get_pod_dict(namespace).values():
                if (
                    pod.metadata.annotations
                    and "orch_id" in pod.metadata.annotations
                    and pod.metadata.annotations["orch_id"] == orchid
                ):
                    futures.append(executor.submit(self._delete_pod_and_wait, pod, dryrun))
        concurrent.futures.wait(futures)
        logging.info("Deletion completed for pods")

        # ConfigMaps
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            configmaps_to_delete = []

            # First collect all configmaps to delete
            for config_map_name, config_map in self._get_config_map_dict(namespace).items():
                if (
                    config_map.metadata.annotations
                    and "orch_id" in config_map.metadata.annotations
                    and config_map.metadata.annotations["orch_id"] == orchid
                ):
                    configmaps_to_delete.append(config_map_name)

            # Then delete them in parallel if not dryrun
            if not dryrun:
                for config_map_name in configmaps_to_delete:
                    future = executor.submit(self._delete_config_map, config_map_name, namespace)
                    futures.append(future)

            # Wait for all deletions to complete
            concurrent.futures.wait(futures)
        logging.info("Deletion completed for configmaps")
