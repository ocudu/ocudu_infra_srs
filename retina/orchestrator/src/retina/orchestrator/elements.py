#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Collection of elements
"""

import contextlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Tuple, Union

RETINA_LABEL = "retina"


# pylint: disable=too-few-public-methods
class TaintDefinition:
    """
    Taint definition
    """

    def __init__(self, key: str, value: str, effect: Union[str, None] = None):
        self.key = key
        self.value = value
        self.effect = effect if effect else "NoSchedule"

    def get_str_taint(self) -> str:
        """
        Get taint as string
        """
        return get_str_taint(self.key, self.value, self.effect)


class KubernetesType(Enum):
    """
    Kubernetes element type
    """

    POD = "pod"
    CONFIGMAP = "configmap"
    SERVICE = "service"
    SECRET = "secret"


class RetinaType(Enum):
    """
    Retina element type
    """

    PORT = "port"
    ORCHID = "orchid"
    POD = "pod"
    RESOURCE_SPACE = "resource_space"
    NONE = ""


class KubernetesElement:
    """
    Data class Kubenretes element
    """

    def __init__(self, data, element_type: KubernetesType):
        """
        Constructor
        """
        self.kubernetes_type = element_type
        self.data = data
        self.retina_type, self.metadata = self.get_retina_type()

    @property
    def name(self):
        """
        Get name
        """
        return self.data.metadata.name

    @property
    def orch_id(self):
        """
        Get orchestration ID
        """
        return self.get_orchestration_id()

    @property
    def user_name(self):
        """
        Get user name
        """
        return self.get_user_name()

    def is_retina(self) -> bool:
        """
        Check if it's a Retina element
        """
        return bool(self.get_orchestration_id())

    def get_age(self) -> float:
        """
        Get age in seconds
        """
        current_time = datetime.now(timezone.utc)
        age_seconds = (current_time - self.data.medatada.creation_timestamp).total_seconds()
        return age_seconds

    def get_retina_type(self) -> Tuple[RetinaType, str]:
        """
        Get retina type
        """
        if not self.is_retina():
            return RetinaType.NONE, ""

        if self.kubernetes_type == KubernetesType.POD:
            return RetinaType.POD, ""
        if self.kubernetes_type == KubernetesType.CONFIGMAP:
            return self.get_retina_configmap_type()

        return RetinaType.NONE, ""

    def get_retina_configmap_type(self) -> Tuple[RetinaType, str]:
        """
        Get retina configmap type
        """
        pattern1 = r"^retina-rs-(\d+)$"
        pattern2 = r"^retina-tst-(\d+)-configmap-port$"
        pattern3 = r"^retina-tst-(\w+)-configmap-orchid$"

        match1 = re.match(pattern1, self.name)
        match2 = re.match(pattern2, self.name)
        match3 = re.match(pattern3, self.name)

        if match1:
            return RetinaType.RESOURCE_SPACE, match1.group(1)
        if match2:
            return RetinaType.PORT, match2.group(1)
        if match3:
            return RetinaType.ORCHID, match3.group(1)

        return RetinaType.NONE, ""

    def get_orchestration_id(self):
        """
        Get the orchestration id
        """
        return self.get_annotation("orch_id")

    def get_user_name(self) -> str:
        """
        Get user name
        """
        return self.get_annotation("user_name")

    def get_annotation(self, key: str) -> str:
        """
        Get annotation
        """
        with contextlib.suppress(Exception):
            return self.data.annotations[key]
        return ""


@dataclass()
class KubernetesElementsCluster:
    """
    Data class that data node info
    """

    pods: List[KubernetesElement]
    configmaps: List[KubernetesElement]


@dataclass()
class LabelDefinition:
    """
    Data class that data label info
    """

    name: str
    value: str
    reverse: bool = False


# pylint: disable=R0913, disable=too-many-instance-attributes
class Node:
    """
    Node definition
    """

    # pylint: disable=too-many-positional-arguments
    def __init__(
        self,
        name: str,
        architecture: str,
        os_image: str,
        kernel_version: str,
        label_list: List[LabelDefinition],
        taint_list: List[TaintDefinition],
        ip_address: str,
        allocatable_cpu: float,
        allocatable_memory: str,
        allocatable_storage: str,
    ):
        self.name = name
        self.ip_address = ip_address
        self.allocatable_cpu = allocatable_cpu
        self.allocatable_memory = allocatable_memory
        self.architecture = architecture
        self.os_image = os_image
        self.kernel_version = kernel_version
        self.label_list = label_list
        self.taint_list = taint_list
        self.allocatable_storage = allocatable_storage

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, Node):
            if self.name == __value.name:
                return True
        return False

    def is_retina_node(self):
        """
        Returns true if the node is a retina node
        """
        for label in self.label_list:
            if label.name == "retina.srs.io/member" and label.value == "true":
                return True
        return False

    def check_label_list(self, label_list: List[LabelDefinition]):
        """
        Check if the label list is in the node
        """
        for label in label_list:
            if label.reverse:
                if label in self.label_list:
                    return False
            else:
                if label not in self.label_list:
                    return False
        return True

    def get_taint_list_as_string(self) -> List[str]:
        """
        Get taint list as string
        """
        return get_taint_list_as_string(self.taint_list)


def get_node_names(node_list: List[Node]) -> List[str]:
    """
    Returns a list of node names
    """
    return [node.name for node in node_list]


def get_str_taint(key: str, value: str, effect: str) -> str:
    """
    Get string taint
    """
    return f"{key}={value}:{effect}"


def get_taint_list_as_string(taint_list: List[TaintDefinition]) -> List[str]:
    """
    Get taint list as string
    """
    return [taint.get_str_taint() for taint in taint_list]
