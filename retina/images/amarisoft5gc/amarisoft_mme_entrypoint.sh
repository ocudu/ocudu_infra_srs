#! /bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


set -e

. amarisoft_mme_setup.sh

mkdir -p /etc/retina/resources
echo """- type: core
  address: 192.168.0.1
  port: 38412
  mask: 24""" > /etc/retina/resources/core_network.yaml

# Retina Agent
exec /usr/local/bin/agent.sh amarisoft-5gc "$@"