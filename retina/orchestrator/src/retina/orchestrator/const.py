# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Constants definition
"""

# Prefix in the name of the cluster elements
ELEMENT_PREFIX = "retina"
# Prefix in the resource space of the cluster elements
RESOURCE_SPACE_PREFIX = "retina-rs"
# Prefix in the resource cluster of the cluster elements
CLUSTER_RESOURCE_SPACE_PREFIX = "retina-rcluster"
# Prefix in the name of the service opening the ports
RESOURCE_DATA_PREFIX = "rdata"
RESOURCE_DATA_FILE = "resource.yml"

# Name of the service opening the ports
PORT_SERVICE_NAME = "retina-service"

NUMBER_PORT_INIT = 32000
NUMBER_OF_PORTS = 700

SERVICE_LOADBALANCER = "loadBalancer"
SERVICE_NODEPORT = "NodePort"
LABEL = "retina-label"

# Pods in privileged mode
PRIVILEGED_MODE = True

CLUSTER_CONFIGURATION_CONFIGMAP_NAME = "retina-info"
DEFAULT_USERNAME = "codeboot"

KUBERNETES_REQUEST_TIMEOUT = 30

TERMINATION_GRACE_PERIOD_SECONDS = 10

DEFAULT_RESERVATION_TIMEOUT = 900

ZMQ_TAINT_LABEL = "retina_zmq"

RETINA_DEPLOY_LABEL_KEY = "retina-deploy"

MAX_NUMBER_OF_EXTRA_PORTS = 8

RESERVATION_NUM_RETRIES = 10

RESERVATION_NUM_SECONDS_BETWEEN_RETRIES = 10
