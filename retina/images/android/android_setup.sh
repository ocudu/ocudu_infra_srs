#! /bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


set -e

DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    adb scrcpy

mkdir -p /root/.android/ && readlink -f $(which adb) >/root/.android/adb.5037
