#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


set -e

# Network configuration
export CORE_IP="${CORE_IP:-10.45.0.1}"
export CORE_NETMASK="${CORE_NETMASK:-24}"

# Run Amarisoft's init script (suppress errors for read-only sysctls)
lte_init.sh 2>/dev/null || true

mkdir -p /etc/retina/resources
echo """- type: core
  address: ${CORE_IP}
  port: 38412
  mask: ${CORE_NETMASK}""" > /etc/retina/resources/core_network.yaml

# Retina Agent
exec /usr/local/bin/agent.sh amarisoft-5gc "$@"
