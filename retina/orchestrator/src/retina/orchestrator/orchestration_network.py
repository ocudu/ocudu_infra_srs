# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Orchestrator manager
"""

import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from retina.orchestrator import configs, const, utils
from retina.orchestrator.const import DEFAULT_RESERVATION_TIMEOUT, MAX_NUMBER_OF_EXTRA_PORTS
from retina.orchestrator.elements import get_taint_list_as_string
from retina.orchestrator.reservation.managers import get_pool_request_reservation_from_config
from retina.orchestrator.reservation.resources import (
    BinaryDefinition,
    NodeResource,
    RequestReservation,
    ResourceList,
    ResourceZmq,
)
from retina.orchestrator.reservation.utils import create_resource_data_configmap, get_resource_data_configmap_name
from retina.orchestrator.retina_kubernetes import DEFAULT_NAMESPACE, ErrorCode, Kubernetes
from retina.orchestrator.timeout_handler import TimeoutHandler
from retina.orchestrator.utils import (
    check_binary_can_exec,
    get_orchid_configmap_name,
    get_pod_name,
    get_port_configmap_name,
    parse_request,
)
from retina.protocol.resource import dump_resource_list_to_str, Node


@dataclass
# pylint: disable=too-many-instance-attributes
class RetinaPod:
    """
    Retina pod
    """

    name: str
    type_deploy: str
    address: str
    port_array: Tuple[int, ...]
    extra_port_array: Tuple[int, ...]
    pod_name: str
    node_name: str
    pod_ip: str
    resource: ResourceList
    node_resource: Node


class OrchestratorManager:
    """
    Orchestrator manager
    """

    _alive_orch_id_list: List[str] = []

    def __init__(self, *args, **kwargs):
        self.k_server = Kubernetes(*args, **kwargs)
        self.namespace = DEFAULT_NAMESPACE

    @classmethod
    def _get_alive_orch_id_list_copy(cls) -> List[str]:
        return list(cls._alive_orch_id_list)

    @classmethod
    def _append_to_alive_orch_id_list(cls, orch_id: str) -> None:
        cls._alive_orch_id_list.append(orch_id)

    @classmethod
    def _remove_from_alive_orch_id_list(cls, orch_id: str) -> None:
        if orch_id in cls._alive_orch_id_list:
            cls._alive_orch_id_list.remove(orch_id)

    ############################################################################
    # Utils
    ############################################################################
    def get_json_output_orchestration(self, setup: Iterable[RetinaPod], orch_id: str):
        """
        Get output declaration for orchestration network
        """

        return {
            "id": orch_id,
            "node_list": [
                {
                    "name": f"{res_inst.name}-{i+1}",
                    "type": res_inst.type_deploy,
                    "address": res_inst.address,
                    "port": int(port),
                    "resources": [
                        *(
                            item
                            for resource in res_inst.resource.get_resources()
                            for item in resource.get_resource_data()
                        ),
                        res_inst.node_resource,
                    ],
                }
                for res_inst in setup
                for i, port in enumerate(res_inst.port_array)
            ],
        }

    ############################################################################
    # Delete
    ############################################################################
    def delete_orchestration_network(self, *orchid_tuple: str):
        """
        Delete orchestration network
        """
        # Delete pods
        # Delete configmap port
        # Delete configmap RS
        # Delete configmap network ID
        for orch_id in set((*self._get_alive_orch_id_list_copy(), *orchid_tuple)):
            self.k_server.delete_all_by_orchid(orch_id, self.namespace, False)
            self._remove_from_alive_orch_id_list(orch_id)

    def delete_orchestration_network_by_username(self, user_name: str, enable_regex: bool):
        """
        Delete orchestration network
        """
        # Delete pods
        # Delete configmap port
        # Delete configmap RS
        # Delete configmap network ID
        orchid_list = self.k_server.get_orch_id_list_by_username(
            user_name_expected=user_name, enable_regex=enable_regex, namespace=self.namespace
        )
        for orchid_inst in orchid_list:
            self.k_server.delete_all_by_orchid(orchid=orchid_inst, namespace=self.namespace, dryrun=False)
        self.k_server.delete_config_map_by_user_name(
            user_name=user_name,
            namespace=self.namespace,
            dryrun=False,
            enable_regex=enable_regex,
        )

    def delete_all_orchestration_network(self, dryrun: bool):
        """
        Delete all orchestration network
        """
        # Delete pods
        # Delete configmap port
        # Delete configmap RS
        # Delete configmap network ID
        orchid_list = self.k_server.get_orch_id_list_by_username(
            user_name_expected=None, enable_regex=False, namespace=self.namespace
        )
        for orchid_inst in orchid_list:
            self.k_server.delete_all_by_orchid(orchid=orchid_inst, namespace=self.namespace, dryrun=dryrun)
        self.k_server.delete_config_map_by_user_name(
            user_name=None, namespace=self.namespace, dryrun=dryrun, enable_regex=False
        )

    ############################################################################
    # Infrastructure
    ############################################################################
    # pylint: disable=R0914, disable=too-many-arguments,  disable=too-many-positional-arguments
    def create_infrastructure(
        self,
        request_path: str,
        timeout: Optional[int] = None,
        user_name=const.DEFAULT_USERNAME,
        print_info=True,
        dev_mode=False,
        not_finite_execution=False,
    ):
        """
        Create infrastructure from request

        :param request_path: request path
        :return infrastructure
        """
        timeout_handler = TimeoutHandler(
            timeout or DEFAULT_RESERVATION_TIMEOUT,
            "Timeout reached while reserving and/or waiting for pods to be ready",
        )

        # Create orchestration network ID
        orch_id = self.get_orchestration_network_id(user_name)
        self._append_to_alive_orch_id_list(orch_id)

        retina_setup: List[RetinaPod] = []
        try:
            req = parse_request(request_path)

            # Get pool request reservation
            pool_request = get_pool_request_reservation_from_config(config=req, orch_id=orch_id, user_name=user_name)

            # Reserve cluster resources
            logging.debug("Looking for cluster resources...")
            pool_request.reserve_cluster_resources(self.k_server, timeout_handler)

            # Reserve node resources
            logging.debug("Looking for node resources...")
            pool_request.reserve_node_resources(self.k_server, timeout_handler)

            # Create orchestration network in parallel
            executor = ThreadPoolExecutor()
            try:
                futures = [
                    executor.submit(
                        self._create_pod_or_deployment_infrastructure,
                        request_reservation=req_reservation,
                        orch_id=orch_id,
                        user_name=user_name,
                        dev_mode=dev_mode,
                        timeout_handler=timeout_handler,
                        not_finite_execution=not_finite_execution,
                    )
                    for req_reservation in pool_request.request_reservation_list
                ]
                for future in futures:
                    retina_setup.append(future.result())
            finally:
                timeout_handler.cancel()
                executor.shutdown(wait=True, cancel_futures=True)

        except Exception as exc:
            self.delete_orchestration_network(orch_id)
            raise exc
        if print_info:
            self.print_orchestration_network_info(orch_id, retina_setup)
        return (
            orch_id,
            retina_setup,
            self.get_json_output_orchestration(retina_setup, orch_id),
        )

    ############################################################################
    # Services
    ############################################################################
    def create_loadbalancer_service(self) -> None:
        """
        Create retina loadbalancer service
        """
        ports = []
        for i in range(const.NUMBER_PORT_INIT, const.NUMBER_PORT_INIT + const.NUMBER_OF_PORTS):
            ports.append({"name": f"port-{i}", "port": i, "targetPort": f"port-{i}"})

        service_config = {
            "name": const.PORT_SERVICE_NAME,
            "selector": const.LABEL,
            "ports": ports,
            "type": const.SERVICE_LOADBALANCER,
        }

        response = self.k_server.create_retina_service(service_config)
        if response == ErrorCode.OK:
            logging.info("LoadBalancer service created.")
        else:
            raise RuntimeError(f"Error creating LoadBalancer service: {response}")

    def create_nodeport_service(self) -> None:
        """
        Create retina nodePort service
        """
        ports = []
        for i in range(const.NUMBER_PORT_INIT, const.NUMBER_PORT_INIT + const.NUMBER_OF_PORTS):
            port_definition = {
                "name": f"port-{i}",
                "port": i,
                "targetPort": f"port-{i}",
                "nodePort": i,
            }
            ports.append(port_definition)

        service_config = {
            "name": const.PORT_SERVICE_NAME,
            "selector": const.LABEL,
            "ports": ports,
            "type": const.SERVICE_NODEPORT,
        }

        response = self.k_server.create_retina_service(service_config)
        if response == ErrorCode.OK:
            logging.info("NodePort service created.")
        else:
            raise RuntimeError(f"Error creating NodePort service: {response}")

    ############################################################################
    # ConfigMap
    ############################################################################
    def reserve_port(self, orch_id: str, user_name: str):
        """
        Create configmap
        """
        # Create config map
        create_check = True

        possible_ports = list(range(const.NUMBER_PORT_INIT, const.NUMBER_PORT_INIT + const.NUMBER_OF_PORTS))

        while create_check:
            port_index = random.randint(0, len(possible_ports) - 1)
            port_number = possible_ports.pop(port_index)

            data = {"orch_id": orch_id, "user_name": user_name}
            config_map_config = configs.ConfigmapConfig(
                orch_id=orch_id, user_name=user_name, timeout=None, data=data, name=get_port_configmap_name(port_number)
            )

            response = self.k_server.create_config_map(config_map_config)
            if response == ErrorCode.OK:
                create_check = False
        return port_number

    def get_orchestration_network_id(self, user_name: str):
        """
        Create orchestration network ID
        """
        orch_id = ""
        create_check = True

        while create_check:
            orch_id, name = get_orchid_configmap_name()
            data = {"orch_id": orch_id, "user_name": user_name}
            config_map_config = configs.ConfigmapConfig(
                orch_id=orch_id, user_name=user_name, timeout=None, data=data, name=name
            )

            response = self.k_server.create_config_map(config_map_config)
            if response == ErrorCode.OK:
                create_check = False
        return orch_id

    ############################################################################
    # Pod
    ############################################################################
    def get_ports(self, nof_ports: int, orch_id: str, user_name: str) -> Tuple[int, ...]:
        """
        Get ports
        """

        if nof_ports != 0:
            with ThreadPoolExecutor() as executor:
                ports = list(executor.map(lambda _: self.reserve_port(orch_id, user_name), range(nof_ports)))
                return tuple(ports)
        return tuple()

    # pylint: disable=too-many-positional-arguments
    def _create_pod_or_deployment_infrastructure(
        self,
        request_reservation: RequestReservation,
        orch_id: str,
        user_name: str,
        dev_mode: bool,
        timeout_handler: TimeoutHandler,
        not_finite_execution: bool,
    ) -> RetinaPod:
        """
        Create Pod

        :param config: configuration
        :return: infrastructure
        """
        ########################################################################
        # Reserve ports
        ########################################################################
        retina_ports = request_reservation.get_nof_ports()
        retina_ports_number_array = self.get_ports(nof_ports=retina_ports, user_name=user_name, orch_id=orch_id)
        extra_ports_number_array = self.get_ports(
            nof_ports=MAX_NUMBER_OF_EXTRA_PORTS, user_name=user_name, orch_id=orch_id
        )

        # Cluster configuration
        networking_mode = self.k_server.get_cluster_configuration()["networking-mode"]
        dns_policy = self.k_server.get_cluster_configuration()["dnsPolicy"]

        ########################################################################
        # Create service if it doesn't exist
        ########################################################################
        if networking_mode == const.SERVICE_LOADBALANCER:
            if self.k_server.get_load_balancer_service() is None:
                self.create_loadbalancer_service()
        else:
            if self.k_server.get_node_port_service() is None:
                self.create_nodeport_service()

        ########################################################################
        # Create configmap RS
        ########################################################################
        node_resource = Node(
            port_array=list(extra_ports_number_array),
            lcores_eal=request_reservation.get_node_configuration(self.k_server),
            node_ip=request_reservation.get_uu_ip(self.k_server),
            backhaul_ip=request_reservation.get_backhaul_ip(self.k_server),
        )
        create_resource_data_configmap(
            k_server=self.k_server,
            name=get_resource_data_configmap_name(request_reservation.name),
            orch_id=orch_id,
            user_name=user_name,
            data={const.RESOURCE_DATA_FILE: dump_resource_list_to_str([node_resource])},
            timeout=int(timeout_handler.get_remaining_timeout()),
        )

        ########################################################################
        # Create Pod
        ########################################################################
        pod_name = get_pod_name(request_reservation.name, orch_id)
        pod_config = configs.PodConfig(
            dns_policy=dns_policy,
            orch_id=orch_id,
            user_name=user_name,
            name=pod_name,
            image=request_reservation.image,
            resource_data_configmap_list=[
                get_resource_data_configmap_name(request_reservation.name),
                *(
                    get_resource_data_configmap_name(resource)
                    for resource in request_reservation.get_reserved_resources().get_resources()
                    if not isinstance(resource, ResourceZmq) and resource.capacity > 0
                ),
            ],
            retina_ports=list(retina_ports_number_array),
            extra_ports=list(extra_ports_number_array),
            privileged=True,
            timeout=int(timeout_handler.get_remaining_timeout()),
            taint_list=request_reservation.get_taints(k_server=self.k_server),
            label_list=request_reservation.get_labels(),
            request_list=request_reservation.get_requirements(k_server=self.k_server),
            node_name=request_reservation.get_node_name(k_server=self.k_server),
            enable_network_connection=request_reservation.get_enable_network_connection(k_server=self.k_server),
            enable_usb_connection=request_reservation.get_enable_usb_connection(),
            enable_pci_connection=request_reservation.get_enable_pci_connection(),
            environment=request_reservation.environment,
            command=request_reservation.command,
            not_finite_execution=not_finite_execution,
            grace_period=request_reservation.grace_period,
        )

        logging.debug(
            "Creating %s for: %s with taints %s",
            "pod" if not dev_mode else "deployment",
            pod_name,
            get_taint_list_as_string(pod_config.taint_list),
        )

        if dev_mode:
            pod = self.k_server.create_deployment_until_pod_scheduled(
                config=pod_config, namespace=DEFAULT_NAMESPACE, timeout_handler=timeout_handler
            )
        else:
            pod = self.k_server.create_pod_until_scheduled(
                config=pod_config, namespace=DEFAULT_NAMESPACE, timeout_handler=timeout_handler
            )
        pod_name = pod.metadata.name
        node_name = pod.spec.node_name
        pod_ip = self.k_server.get_pod_ip(pod_name)  # it could take some extra time to have a pod IP assigned

        # Get pod name and IP
        if self.k_server.is_incluster():
            load_balancer_ip = pod_ip
        else:
            if networking_mode == const.SERVICE_LOADBALANCER:
                load_balancer_ip = self.k_server.get_load_balancer_ip()
            else:
                load_balancer_ip = self.k_server.get_node_ip_dict(node_name)["InternalIP"]

        # Copy binary
        self.copy_binaries(request_reservation.get_binaries(), pod_name)

        if not not_finite_execution:
            self.check_pod_port_list(load_balancer_ip, retina_ports_number_array, timeout_handler)

        retina_pod = RetinaPod(
            name=request_reservation.name,
            type_deploy=request_reservation.type_r,
            address=pod_ip if self.k_server.is_incluster() else load_balancer_ip,
            port_array=tuple(retina_ports_number_array),
            extra_port_array=tuple(extra_ports_number_array),
            pod_name=pod_name,
            node_name=node_name,
            pod_ip=pod_ip,
            resource=ResourceList(
                [
                    r
                    for r in request_reservation.get_reserved_resources().get_resources()
                    if not isinstance(r, ResourceZmq) and r.capacity > 0
                ]
            ),
            node_resource=node_resource,
        )
        if dev_mode:
            logging.info("Deployment ready: %s", retina_pod.pod_name)
        else:
            logging.debug("Pod ready: %s", retina_pod.pod_name)

        return retina_pod

    def copy_binaries(self, binary_list: List[BinaryDefinition], pod_name: str):
        """
        Copy binaries to pod
        """
        for binary_inst in binary_list:
            local_path = binary_inst.local_path
            remote_path = binary_inst.remote_path

            if not os.path.exists(local_path) and not binary_inst.is_optional:
                raise RuntimeError(f"Binary path doesn't exist: {local_path}")

            # Check execution permissions
            if binary_inst.is_executable:
                check_binary_can_exec(local_path)

            msg = f'Copying local folder "{local_path}" to "{remote_path}" {pod_name}'
            logging.debug(msg)
            # Copy binary
            self.k_server.copy_to_pod(local_path, remote_path, pod_name, DEFAULT_NAMESPACE)
            logging.debug("Copied!")

    def print_orchestration_network_info(self, orch_id: str, retina_setup: Iterable[RetinaPod]):
        """
        Show orchestration network information
        """
        msg = f"""
*************************************************************
Ochestration network ID = {orch_id}
*************************************************************
"""
        for pod in retina_setup:
            name = pod.name
            address = pod.address
            port = ",".join(map(str, pod.port_array))
            pod_node = str(pod.node_name)

            space = None
            for resource in pod.resource.get_resources():
                if isinstance(resource, NodeResource):
                    space = resource.space

            msg += f"""- Name: {name}
- Address: {address}:{port}
- Node name: {pod_node}
- Resource space: {space}
*************************************************************    
"""
        logging.debug(msg)

    def check_pod_port_list(
        self, ip_add: str, port_number_array: Optional[Tuple], timeout_handler: TimeoutHandler
    ) -> bool:
        """
        Check port list
        """
        # Check if pod ports are alive
        if port_number_array is None:
            return True
        while timeout_handler.not_reached():
            if utils.check_port_list(ip_add, port_number_array):
                return True
            time.sleep(1)
        return False
