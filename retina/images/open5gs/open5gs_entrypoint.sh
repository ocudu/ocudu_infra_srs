#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


. open5gs_teardown.sh
. open5gs_setup.sh

# Retina Agent
##############
_term() {
    echo "Caught SIGTERM signal!"
    kill -TERM "$child" 2>/dev/null
}

mkdir -p /etc/retina/resources
echo """- type: core
  address: $TUN_IP_PREFIX.0.1
  port: 38412
  mask: $TUN_MASK""" > /etc/retina/resources/core_network.yaml

trap _term SIGTERM SIGINT

/usr/local/bin/agent.sh open5gs-5gc --maximum-workers 96 $@ &

child=$!
wait "$child"

. open5gs_teardown.sh
