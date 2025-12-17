#! /bin/bash
#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


set -e

. amarisoft_ue_setup.sh

# Retina Agent
exec /usr/local/bin/agent.sh amarisoft-ue --maximum-workers 96 "$@"