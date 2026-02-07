#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

# pylint: disable=too-many-lines, disable=too-many-positional-arguments
"""
Resources elements
"""

import logging
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from time import sleep
from typing import Any, Dict, List, Optional, Union

from retina.protocol.redact import add_log_secret
from retina.protocol.resource import (
    Accelerator,
    API,
    Core,
    dump_resource_list_to_str,
    License,
    Remote,
    Ru,
    Sdr,
    Ue,
)

from retina.orchestrator import const
from retina.orchestrator.const import (
    RESERVATION_NUM_RETRIES,
    RESERVATION_NUM_SECONDS_BETWEEN_RETRIES,
    TERMINATION_GRACE_PERIOD_SECONDS,
)
from retina.orchestrator.elements import Node, TaintDefinition
from retina.orchestrator.kubernetes import KUBERNETES_SKIP_TAINT_ARRAY
from retina.orchestrator.requirement import RequirementDefinition, RequirementManager
from retina.orchestrator.reservation.utils import (
    create_resource_data_configmap,
    get_cluster_resource_name,
    get_resource_data_configmap_name,
    get_space_name,
    reserve_cluster_resource_configmap,
)
from retina.orchestrator.retina_kubernetes import Kubernetes

################################################################################
# Types
################################################################################


class RetinaResourceType(Enum):
    """
    Retina resource group
    """

    NODE = "nodeResource"
    CLUSTER = "clusterResource"


class ConnectionType(Enum):
    """
    Connection type
    """

    USB = "usb"
    NETWORK = "network"
    PCI = "pci"


@dataclass
class BinaryDefinition:
    """
    Binary definition
    """

    local_path: str
    remote_path: str
    is_executable: bool
    is_optional: bool


################################################################################
# Global resource
################################################################################
class Resource(ABC):
    """
    Resource manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        type_r: str,
        model: str,
        capacity: int = 1,
        retina_resource_type: Optional[RetinaResourceType] = None,
        connection: Optional[ConnectionType] = None,
    ):
        self.capacity = capacity
        self.retina_resource_type = retina_resource_type
        self.type_r = type_r
        self.model = model
        self.connection = connection
        self.id_name: Optional[str] = None

    def set_id(self, id_name: Optional[str]):
        """
        Set id_name
        """
        self.id_name = id_name

    def get_id(self) -> Optional[str]:
        """
        Get id_name
        """
        return self.id_name

    def is_cluster_resource(self):
        """
        Returns true if the resource is a cluster resource
        """
        return self.retina_resource_type == RetinaResourceType.CLUSTER

    def is_zmq_resource(self):
        """
        Returns true if the resource is a zmq resource
        """
        return self.type_r == "zmq"

    def __contains__(self, element):
        return self.__eq__(element)

    @abstractmethod
    def reserve(
        self, k_server: Kubernetes, num_of_retry: int, num_seconds_per_retry, orch_id: str, user_name: str, timeout: int
    ) -> bool:
        """
        Reserve resource
        """

    @abstractmethod
    def is_available(self, kubernetes: Kubernetes) -> bool:
        """
        Check if the resource is available
        """


################################################################################
# Cluster resource
################################################################################
class ClusterResource(Resource):
    """
    Cluster resource manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        type_r: str = License.__name__,
        connection: Optional[ConnectionType] = None,
    ):
        super().__init__(
            capacity=capacity,
            retina_resource_type=RetinaResourceType.CLUSTER,
            type_r=type_r,
            model=model,
            connection=connection,
        )

    def get_full_name(self) -> str:
        """
        Get full name
        """
        return f"{self.type_r}-{self.model}".lower()

    def is_available(self, kubernetes: Kubernetes) -> bool:
        """
        Check if the resource is available
        """
        if kubernetes.config_map_exists(get_cluster_resource_name(self.get_full_name())):
            return False
        return True

    def get_user_name(self, kubernetes: Kubernetes) -> str:
        """
        Get user name
        """
        return kubernetes.get_config_map(get_cluster_resource_name(self.get_full_name())).data.get("user_name", "")

    def __eq__(self, value) -> bool:
        """
        Equal
        """
        try:
            if (
                self.retina_resource_type == value.retina_resource_type
                and self.type_r == value.type_r
                and re.match(f"^{self.model}$", value.model) is not None
            ):
                return True
        except AttributeError:
            return False
        return False

    def __hash__(self):
        return hash((self.type_r, self.model, str(self.capacity), self.connection))

    def reserve(
        self, k_server: Kubernetes, num_of_retry: int, num_seconds_per_retry, orch_id: str, user_name: str, timeout: int
    ) -> bool:
        """
        Reserve resource
        """

        if self.capacity is None or self.capacity <= 0:
            return True

        for _ in range(0, num_of_retry):
            result = reserve_cluster_resource_configmap(
                k_server=k_server,
                name=self.get_full_name(),
                orch_id=orch_id,
                user_name=user_name,
                timeout=timeout,
            )
            if not result:
                sleep(num_seconds_per_retry)
            else:
                return create_resource_data_configmap(
                    k_server=k_server,
                    name=get_resource_data_configmap_name(self),
                    orch_id=orch_id,
                    user_name=user_name,
                    data={const.RESOURCE_DATA_FILE: dump_resource_list_to_str(self.get_resource_data())},
                    timeout=timeout,
                )
        return False

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return []


class ResourceLicense(ClusterResource):
    """
    Resource license manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        ip_address: Optional[str] = None,
        args: Optional[str] = None,
    ):
        super().__init__(
            capacity=capacity,
            type_r=License.__name__,
            model=model,
            connection=ConnectionType.NETWORK,
        )
        add_log_secret(ip_address)
        self.ip_address = ip_address
        self.args = args

    def __hash__(self):
        return hash((self.type_r, self.model, str(self.capacity), self.args, self.connection, self.ip_address))

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return [License(address=self.ip_address, args=self.args)]


class ResourceRemote(ClusterResource):
    """
    Resource remote manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        address: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        path: Optional[str] = None,
    ):
        super().__init__(
            capacity=capacity,
            type_r=Remote.__name__,
            model=model,
            connection=ConnectionType.NETWORK,
        )
        add_log_secret(user)
        self.user = user
        add_log_secret(password)
        self.password = password
        self.address = address
        self.path = path

    def __hash__(self):
        return hash(
            (
                self.type_r,
                self.model,
                str(self.capacity),
                self.connection,
                self.user,
                self.password,
                self.address,
                self.path,
            )
        )

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return [Remote(address=self.address, user=self.user, password=self.password, path=self.path)]


class ResourceAPI(ClusterResource):
    """
    Resource API manager
    """

    def __init__(
        self,
        model: str,
        capacity: int = 1,
        address: Optional[str] = None,
        port: Optional[int] = None,
    ):
        super().__init__(
            capacity=capacity,
            type_r=API.__name__,
            model=model,
            connection=ConnectionType.NETWORK,
        )
        self.address = address
        self.port = port

    def __hash__(self):
        return hash((self.type_r, self.model, str(self.capacity), self.connection, self.address, self.port))

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return [API(address=self.address, port=self.port)]


class ResourceCore(ClusterResource):
    """
    Resource core manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        address: Optional[str] = None,
        port: Optional[int] = None,
        mask: Optional[int] = None,
    ):
        super().__init__(
            capacity=capacity,
            type_r=Core.__name__,
            model=model,
            connection=ConnectionType.NETWORK,
        )
        self.address = address
        self.port = port
        self.mask = mask

    def __hash__(self):
        return hash((self.type_r, self.model, str(self.capacity), self.connection, self.address, self.port, self.mask))

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return [Core(address=self.address, port=self.port, mask=self.mask)]


################################################################################
# Cluster resource
################################################################################
class NodeResource(Resource):
    """
    Node resource manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        type_r: str,
        model: str,
        capacity: int = 1,
        connection: Optional[ConnectionType] = None,
        space: Optional[int] = None,
        node: Optional[Node] = None,
    ):
        super().__init__(
            capacity=capacity,
            retina_resource_type=RetinaResourceType.NODE,
            type_r=type_r,
            model=model,
            connection=connection,
        )
        self.space = space
        self.node = node

    def get_full_name(self) -> str:
        """
        Get full name
        """
        return f"{self.type_r}-{self.model}:{self.space}".lower()

    def is_available(self, kubernetes: Kubernetes) -> bool:
        """
        Check if the resource is available
        """
        if self.space is None:
            return False

        # Reload node information in case it has changed
        if self.node is not None:
            # If the node is unreachable, the resource is not available
            node = kubernetes.get_retina_node_dict(only_retina_labels=False, skip_not_available=False).get(
                self.node.name, None
            )
            if node is not None:
                if node.taint_list in KUBERNETES_SKIP_TAINT_ARRAY:
                    return False
        return not kubernetes.config_map_exists(get_space_name(self.space))

    def __eq__(self, value) -> bool:
        try:
            if (
                self.retina_resource_type == value.retina_resource_type
                and self.type_r == value.type_r
                and re.match(f"^{self.model}$", value.model) is not None
            ):
                return True
        except AttributeError:
            return False
        return False

    def __hash__(self):
        return hash((self.type_r, self.model, str(self.capacity), self.connection, str(self.space)))

    def reserve(
        self, k_server: Kubernetes, num_of_retry: int, num_seconds_per_retry, orch_id: str, user_name: str, timeout: int
    ) -> bool:
        """
        Reserve resource
        """
        if self.capacity is None or self.capacity <= 0:
            return True

        for _ in range(0, num_of_retry):
            result = create_resource_data_configmap(
                k_server=k_server,
                name=get_resource_data_configmap_name(self),
                orch_id=orch_id,
                user_name=user_name,
                data={const.RESOURCE_DATA_FILE: dump_resource_list_to_str(self.get_resource_data())},
                timeout=timeout,
            )
            if result:
                return True
            sleep(num_seconds_per_retry)
        return False

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return []


class ResourceSDR(NodeResource):
    """
    SDR resource manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        space: Optional[int] = None,
        node: Optional[Node] = None,
        connection: Optional[ConnectionType] = None,
        args: Optional[str] = None,
        sample_rate: Optional[int] = None,
        tx_gain: Optional[int] = None,
        rx_gain: Optional[int] = None,
        sync: Optional[str] = None,
    ):
        super().__init__(
            capacity=capacity, type_r=Sdr.__name__, model=model, connection=connection, space=space, node=node
        )

        add_log_secret(args)
        self.args = args
        self.sample_rate = sample_rate
        self.tx_gain = tx_gain
        self.rx_gain = rx_gain
        self.sync = sync

    def __hash__(self):
        return hash(
            (
                self.type_r,
                self.model,
                str(self.capacity),
                self.connection,
                str(self.space),
                self.args,
            )
        )

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return [
            Sdr(
                model=self.model,
                args=self.args,
                sample_rate=self.sample_rate,
                tx_gain=self.tx_gain,
                rx_gain=self.rx_gain,
                sync=self.sync,
            )
        ]


# pylint: disable=too-many-instance-attributes
class ResourceRU(NodeResource):
    """
    RU resource manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        space: Optional[int] = None,
        node: Optional[Node] = None,
        ip_address: Optional[str] = None,
        network_interface: Optional[List[str]] = None,
        du_mac_addr: Optional[List[str]] = None,
        ru_mac_addr: Optional[List[str]] = None,
        vlan_tag_up: Optional[List[str]] = None,
        vlan_tag_cp: Optional[List[str]] = None,
        prach_port_id: Optional[str] = None,
        dl_port_id: Optional[str] = None,
        ul_port_id: Optional[str] = None,
    ):
        super().__init__(
            capacity=capacity,
            type_r=Ru.__name__,
            model=model,
            connection=ConnectionType.NETWORK,
            space=space,
            node=node,
        )
        self.ip_address = ip_address
        self.network_interface = network_interface
        self.du_mac_addr = du_mac_addr
        self.ru_mac_addr = ru_mac_addr
        self.vlan_tag_up = vlan_tag_up
        self.vlan_tag_cp = vlan_tag_cp
        self.prach_port_id = prach_port_id
        self.dl_port_id = dl_port_id
        self.ul_port_id = ul_port_id

    def __hash__(self):
        return hash(
            (
                self.type_r,
                self.model,
                str(self.capacity),
                self.connection,
                str(self.space),
                self.ip_address,
                tuple(self.network_interface) if self.network_interface is not None else None,
                tuple(self.du_mac_addr) if self.du_mac_addr is not None else None,
                tuple(self.ru_mac_addr) if self.ru_mac_addr is not None else None,
                tuple(self.vlan_tag_up) if self.vlan_tag_up is not None else None,
                tuple(self.vlan_tag_cp) if self.vlan_tag_cp is not None else None,
                self.prach_port_id,
                self.dl_port_id,
                self.ul_port_id,
            )
        )

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return [
            Ru(
                model=self.model,
                address=self.ip_address,
                network_interface=self.network_interface,
                ru_mac_address=self.ru_mac_addr,
                du_mac_address=self.du_mac_addr,
                vlan_tag_up=self.vlan_tag_up,
                vlan_tag_cp=self.vlan_tag_cp,
                prach_port_id=self.prach_port_id,
                dl_port_id=self.dl_port_id,
                ul_port_id=self.ul_port_id,
            )
        ]


# pylint: disable=too-many-instance-attributes
class ResourceAccelerator(NodeResource):
    """
    Resource accelerator manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        space: Optional[int] = None,
        node: Optional[Node] = None,
        hwacc_type: Optional[str] = None,
        accelerator_id: Optional[int] = None,
        pdsch_enc_nof_hwacc: Optional[str] = None,
        cb_mode: Optional[bool] = None,
        pusch_dec_nof_hwacc: Optional[int] = None,
        harq_context_size: Optional[int] = None,
        extra_eal_args: Optional[str] = None,
    ):
        super().__init__(
            capacity=capacity,
            type_r=Accelerator.__name__,
            model=model,
            connection=ConnectionType.PCI,
            space=space,
            node=node,
        )
        self.hwacc_type = hwacc_type
        add_log_secret(str(accelerator_id))
        self.accelerator_id = accelerator_id
        self.pdsch_enc_nof_hwacc = pdsch_enc_nof_hwacc
        self.cb_mode = cb_mode
        self.pusch_dec_nof_hwacc = pusch_dec_nof_hwacc
        self.harq_context_size = harq_context_size
        self.extra_eal_args = extra_eal_args

    def __hash__(self):
        return hash((self.type_r, self.model, str(self.capacity), self.connection, str(self.space)))

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return [
            Accelerator(
                model=self.model,
                id=self.accelerator_id,
                cb_mode=self.cb_mode,
                hwacc_type=self.hwacc_type,
                pdsch_enc_nof_hwacc=self.pdsch_enc_nof_hwacc,
                pusch_dec_nof_hwacc=self.pusch_dec_nof_hwacc,
                harq_context_size=self.harq_context_size,
                args=self.extra_eal_args,
            )
        ]


class ResourceAndroid(NodeResource):
    """
    Android resource manager
    """

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        space: Optional[int] = None,
        node: Optional[Node] = None,
        connection: Optional[ConnectionType] = None,
        serial_id: Optional[str] = None,
        imsi: Optional[int] = None,
        k: Optional[str] = None,
        amf: Optional[str] = None,
        opc: Optional[str] = None,
        adb_key: Optional[str] = None,
    ):
        super().__init__(
            capacity=capacity,
            type_r="android",
            model=model,
            connection=connection,
            space=space,
            node=node,
        )
        add_log_secret(serial_id)
        self.serial_id = serial_id
        self.imsi = imsi
        self.k = k
        self.amf = amf
        self.opc = opc
        add_log_secret(adb_key)
        self.adb_key = adb_key

    def __hash__(self):
        return hash((self.type_r, self.model, str(self.capacity), self.connection, str(self.space), self.serial_id))

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        return [
            Ue(
                model=self.model,
                serial_id=self.serial_id,
                imsi=self.imsi,
                k=self.k,
                amf=self.amf,
                opc=self.opc,
                adb_key=self.adb_key,
            )
        ]


class ResourceZmq(NodeResource):
    """
    ZMQ resource manager
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        model: str,
        capacity: int = 1,
        space: Optional[int] = None,
        node: Optional[Node] = None,
    ):
        super().__init__(
            capacity=capacity, type_r="zmq", node=node, connection=ConnectionType.NETWORK, space=space, model=model
        )


################################################################################
# Common
################################################################################
ResourceType = Union[
    ResourceLicense, ResourceSDR, ResourceAndroid, ResourceZmq, ResourceRU, ResourceEmulator, ResourceAccelerator
]


class ResourceList:
    """
    Resource list
    """

    def __init__(self, resources: List[ResourceType]):
        self.resources: List[ResourceType] = resources

    def get_resources(self) -> List[ResourceType]:
        """
        Get resources
        """
        return self.resources

    def set_id(self, id_name: Optional[str]):
        """
        Set id
        """
        for resource in self.resources:
            resource.set_id(id_name=id_name)

    def add_resource(self, resource: ResourceType):
        """
        Add resource
        """
        self.resources.append(resource)

    def get_nof_resources(self) -> int:
        """
        Get number of resources
        """
        return len(self.resources)

    # pylint: disable=too-many-arguments
    def reserve(
        self,
        kubernetes: Kubernetes,
        orch_id: str,
        user_name: str,
        timeout_seconds: int,
        num_of_retry: int = RESERVATION_NUM_RETRIES,
        num_seconds_per_retry=RESERVATION_NUM_SECONDS_BETWEEN_RETRIES,
    ) -> bool:
        """
        Reserve resources
        """

        return all(
            (
                resource.reserve(
                    k_server=kubernetes,
                    orch_id=orch_id,
                    user_name=user_name,
                    timeout=timeout_seconds,
                    num_of_retry=num_of_retry,
                    num_seconds_per_retry=num_seconds_per_retry,
                )
                for resource in self.resources
            )
        )

    def get_resource_data(self) -> List:
        """
        Get resource data
        """
        resource_data: List = []
        for resource in self.resources:
            resource_data.extend(resource.get_resource_data())
        return resource_data

    def __str__(self) -> str:
        """
        String representation
        """
        rep_list = []
        for resource in self.resources:
            rep_list.append(str(resource))
        return f"{rep_list}"


################################################################################
# Reservation
################################################################################
# pylint: disable=too-many-instance-attributes
class RequestReservation:
    """
    Request reservation
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        name: str,
        type_r: str,
        image: str,
        nof_ports: int,
        labels: List[str],
        resources: ResourceList,
        requirement_manager: RequirementManager,
        binary_list: List[BinaryDefinition],
        environment: List[Dict],
        enable_host_network_force: str = "",
        command: Union[None, List[str]] = None,
        force_external_ip: Union[None, bool] = None,
        grace_period: float = TERMINATION_GRACE_PERIOD_SECONDS,
    ):
        """
        Constructor
        """
        self.name = name
        self.type_r = type_r
        self.image = image
        self.nof_ports = nof_ports
        self.labels = labels
        self.resources = resources
        self.requirement_manager = requirement_manager
        self.reserved_resources = ResourceList([])
        self.binary_list = binary_list
        self.environment = environment
        self.enable_host_network_force = enable_host_network_force
        self.command = command
        self.force_external_ip = force_external_ip
        self.grace_period = grace_period
        self._node: Optional[Node] = None

    def get_binaries(self) -> List[BinaryDefinition]:
        """
        Get binaries
        """
        return self.binary_list

    def get_enable_usb_connection(self) -> bool:
        """
        Get enable usb connection
        """
        for resource in self.reserved_resources.get_resources():
            if resource.capacity > 0 and resource.connection == ConnectionType.USB:
                return True
        return False

    def get_enable_pci_connection(self) -> bool:
        """
        Get enable pci connection
        """
        for resource in self.reserved_resources.get_resources():
            if resource.capacity > 0 and resource.connection == ConnectionType.PCI:
                return True
        return False

    def get_enable_network_connection(self) -> str:
        """
        Get enable network connection
        """
        if self.enable_host_network_force:
            return self.enable_host_network_force
        if self.get_enable_usb_connection() or self.get_enable_pci_connection():
            return "InternalIP"
        return ""

    def get_node_name(self, k_server: Kubernetes) -> str:
        """
        Get node name for the reservation
        """
        return self._get_node(k_server=k_server).name

    def get_node_configuration(self, k_server: Kubernetes) -> str:
        """
        Get node configuration
        """
        node_name = self.get_node_name(k_server=k_server)
        for node in k_server.get_cluster_configuration()["nodes"]:
            if node["name"] == node_name and "cpu_isolation" in node:
                return node["cpu_isolation"].get("lcores_eal_args", "")
        return ""

    def _get_node(self, k_server: Kubernetes) -> Node:
        if self._node is None:
            self._node = self._match_node(k_server=k_server)
        return self._node

    # pylint: disable=too-many-branches
    def _match_node(self, k_server: Kubernetes) -> Node:

        node_match_list: List[Node] = []
        node_dict = k_server.get_retina_node_dict(only_retina_labels=False, skip_not_available=True)

        # if there is a label with hostname we get the taints from the node
        label_list = self.requirement_manager.get_label_list()
        for label in label_list:
            if label.name == "kubernetes.io/hostname":
                node_name = label.value
                if node_name in node_dict:
                    return node_dict[node_name]

        reserved_node_resources = [r for r in self.reserved_resources.get_resources() if not r.is_cluster_resource()]
        if len(reserved_node_resources) == 0:
            # No resources in the request search for general nodes
            for node in node_dict.values():
                node_match_list.append(node)
        else:
            for reserved_resource in reserved_node_resources:
                if not reserved_resource.is_cluster_resource():
                    return reserved_resource.node  # type: ignore

        node_match_list_copy = node_match_list.copy()
        for node in node_match_list:
            if not node.check_label_list(self.requirement_manager.get_label_list()):
                node_match_list_copy.remove(node)

        if len(node_match_list_copy) == 0:
            label_list = ""
            for label in self.requirement_manager.get_label_list():
                label_list += f"{label.name}={label.value}, "

            logging.error("Looking for nodes with labels: %s", label_list)
            logging.error(get_nodelist_status(node_dict.values()))
            raise RuntimeError("No node found")

        return node_match_list_copy[random.randint(0, len(node_match_list_copy) - 1)]

    def get_taints(self, k_server: Kubernetes) -> List[TaintDefinition]:
        """
        Get taints
        """
        return self._get_node(k_server=k_server).taint_list

    def get_labels(self) -> List[str]:
        """
        Get labels
        """
        return self.requirement_manager.get_label_list()

    def get_requirements(self, k_server: Kubernetes) -> List[RequirementDefinition]:
        """
        Get labels
        """
        node_name = self.get_node_name(k_server=k_server)
        node_requirements: Dict[str, Any] = {}

        for req in self.requirement_manager.req_list:
            for attr_name, value in {"requests": req.requests, "limits": req.limits}.items():
                if str(value).endswith("%"):
                    if not node_requirements:
                        node_requirements = get_compute_resources_for_node_from_cluster_info(k_server, node_name)
                        if not node_requirements:
                            raise RuntimeError(
                                "Cannot convert percentage requirements to values if the node is not known"
                            )

                    match = re.match(r"^([\d.]+)([a-zA-Z]*)$", str(node_requirements.get(req.name, 0)))
                    if match:
                        total_value = float(match.group(1))
                        suffix = match.group(2)
                    else:
                        total_value = 0
                        suffix = ""
                    setattr(req, attr_name, str(total_value * float(str(value).strip("%")) * 0.01) + suffix)

        return self.requirement_manager.req_list

    def get_nof_ports(self):
        """
        Get ports
        """
        return self.nof_ports

    def add_reserved_resource_list(self, resource_list: ResourceList):
        """
        Add reserved resource list
        """
        for resource in resource_list.get_resources():
            self.reserved_resources.add_resource(resource)

    def add_reserved_resource(self, resource: ResourceType):
        """
        Add reserved resource
        """
        self.reserved_resources.add_resource(resource)

    def set_reserved_resources(self, resources: ResourceList):
        """
        Set reserved resources
        """
        self.reserved_resources = resources

    def get_resources(self) -> ResourceList:
        """
        Get resources
        """
        self.resources.set_id(self.name)
        return self.resources

    def get_reserved_resources(self) -> ResourceList:
        """
        Get reserved resources
        """
        return self.reserved_resources


################################################################################
# Reservation
################################################################################
# pylint: disable=too-many-return-statements
def get_resource_from_config(config: Dict) -> ResourceType:
    """
    Get resource from config
    """
    config_type = config["type"]  # mandatory
    config_model = config.get("model", ".*")
    config_capacity = int(not config.get("dummy", False))

    return {
        # Cluster resources
        "license": ResourceLicense,
        "remote": ResourceRemote,
        "api": ResourceAPI,
        "core": ResourceCore,
        # Most common node resources
        "sdr": ResourceSDR,
        "ru": ResourceRU,
        "accelerator": ResourceAccelerator,
        "android": ResourceAndroid,
        "zmq": ResourceZmq,
    }[config_type](model=config_model, capacity=config_capacity)


# pylint: disable=too-many-branches
def get_resource_from_cluster_info(cluster_info, node_dict: Dict[str, Node]) -> ResourceList:
    """
    Get resource
    """
    resource_list = ResourceList([])

    cluster_resources = cluster_info["cluster_resource_list"]
    for resource in cluster_resources:
        if resource["type"] == "license":
            resource_obj_i = ResourceLicense(
                model=resource["model"],
                ip_address=resource["address"],
                args=resource["args"],
            )
            resource_list.add_resource(resource_obj_i)
        if resource["type"] == "remote":
            resource_obj_j = ResourceRemote(
                model=resource["model"],
                user=resource["user"],
                password=resource["password"],
                address=resource["address"],
                path=resource["path"],
            )
            resource_list.add_resource(resource_obj_j)
        if resource["type"] == "api":
            resource_obj_k = ResourceAPI(
                model=resource["model"],
                address=resource["address"],
                port=resource["port"],
            )
            resource_list.add_resource(resource_obj_k)
        if resource["type"] == "core":
            resource_obj_l = ResourceCore(
                model=resource["model"],
                address=resource["address"],
                port=resource["port"],
                mask=resource["mask"],
            )
            resource_list.add_resource(resource_obj_l)

    for node in cluster_info["nodes"]:
        node_name = node["name"]
        node_in_cluster = node_dict.get(node_name, None)
        if node_in_cluster is not None:
            for resource in node.get("resources", tuple()):
                if resource["type"] == "sdr":
                    resource_list.add_resource(
                        ResourceSDR(
                            model=resource["model"],
                            space=resource["space"],
                            node=node_in_cluster,
                            connection=ConnectionType[resource["connection"].upper()],
                            args=resource["args"],
                            sample_rate=resource["sample_rate"],
                            tx_gain=resource["tx_gain"],
                            rx_gain=resource["rx_gain"],
                            sync=resource["sync"],
                        )
                    )
                elif resource["type"] == "android":
                    resource_list.add_resource(
                        ResourceAndroid(
                            model=resource["model"],
                            space=resource["space"],
                            node=node_in_cluster,
                            connection=ConnectionType[resource["connection"].upper()],
                            serial_id=resource["serial_id"],
                            imsi=resource["imsi"],
                            k=resource["k"],
                            amf=resource["amf"],
                            opc=resource["opc"],
                            adb_key=resource["adb_key"],
                        )
                    )
                elif resource["type"] == "ru":
                    resource_list.add_resource(
                        ResourceRU(
                            model=resource["model"],
                            space=resource["space"],
                            node=node_in_cluster,
                            ip_address=resource["address"],
                            network_interface=resource["network_interface"],
                            du_mac_addr=resource["du_mac_addr"],
                            ru_mac_addr=resource["ru_mac_addr"],
                            vlan_tag_up=resource["vlan_tag_up"],
                            vlan_tag_cp=resource["vlan_tag_cp"],
                            prach_port_id=resource["prach_port_id"],
                            dl_port_id=resource["dl_port_id"],
                            ul_port_id=resource["ul_port_id"],
                        )
                    )
                elif resource["type"] == "accelerator":
                    resource_list.add_resource(
                        ResourceAccelerator(
                            model=resource["model"],
                            space=resource["space"],
                            node=node_in_cluster,
                            hwacc_type=resource["hwacc_type"],
                            accelerator_id=resource["accelerator_id"],
                            pdsch_enc_nof_hwacc=resource["pdsch_enc_nof_hwacc"],
                            cb_mode=resource["cb_mode"],
                            pusch_dec_nof_hwacc=resource["pusch_dec_nof_hwacc"],
                            harq_context_size=resource["harq_context_size"],
                            extra_eal_args=resource.get("extra_eal_args", ""),
                        )
                    )
                elif resource["type"] == "zmq":
                    resource_list.add_resource(
                        ResourceZmq(model=resource["model"], space=resource["space"], node=node_in_cluster)
                    )

    return resource_list


def get_compute_resources_for_node_from_cluster_info(
    k_server: Kubernetes, node_name: str
) -> Dict[str, RequirementDefinition]:
    """
    Get compute-resources for node
    """
    for node in k_server.get_cluster_configuration()["nodes"]:
        if node["name"] == node_name and "compute-resources" in node:
            return node.get("compute-resources", {})
    return {}


def get_nodelist_status(node_list: List[Node]) -> str:
    """
    Get node list status
    """
    message_status = ""
    for node in node_list:
        message_status += f"Node {node.name} does not match the requirements with status:"
        message_status += f"    - Allocatable CPU: {node.allocatable_cpu}"
        message_status += f"    - Allocatable Memory: {node.allocatable_memory}"
        message_status += f"    - Allocatable Memory: {node.allocatable_memory}"
        message_status += f"    - Allocatable Storage: {node.allocatable_storage}"
        message_status += f"    - Taint list: {node.get_taint_list_as_string()}"

        labels_as_string = ""
        for label in node.label_list:
            message_status += f"{label.name}={label.value}, "
        message_status += f"    - Label list: {labels_as_string}"
    return message_status
