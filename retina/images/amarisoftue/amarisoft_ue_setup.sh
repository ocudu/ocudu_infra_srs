#! /bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


set -e

# Set up TUN device inside the container
(mkdir -p /dev/net && mknod /dev/net/tun c 10 200 >/dev/null 2>&1) || true
