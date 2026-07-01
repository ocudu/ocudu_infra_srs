#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

set -e

wait_for_path() {
    local path="$1"
    for _ in $(seq 1 1800); do
        [ -e "$path" ] && return 0
        echo "Waiting for ${path}..."
        sleep 1
    done
    echo "ERROR: Timed out waiting for ${path}" >&2
    return 1
}

# Network configuration
export CORE_IP="${CORE_IP:-10.45.0.1}"
export CORE_NETMASK="${CORE_NETMASK:-24}"

# Wait for amarisoft binaries
amarisoft_dir=/builds/amarisoft/bin
wait_for_path "$amarisoft_dir"

# Install amarisoft binaries
amarisoft_tmp=$(mktemp -d)
cp -r "$amarisoft_dir"/. "$amarisoft_tmp"/
"$amarisoft_tmp"/install.sh --default --no-srv --no-ht --no-all --mme --ims --simserver --no-package /opt/amarisoft
rm -rf "$amarisoft_tmp"

# Run Amarisoft's init script (suppress errors for read-only sysctls)
/opt/amarisoft/mme/lte_init.sh || true

mkdir -p /etc/retina/resources
echo """- type: core
  address: ${CORE_IP}
  port: 38412
  mask: ${CORE_NETMASK}""" > /etc/retina/resources/core_network.yaml

# Retina Agent
exec /usr/local/bin/agent.sh amarisoft-5gc "$@"
