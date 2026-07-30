#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


set -e

DEBIAN_FRONTEND=noninteractive apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates wget
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    adb scrcpy

mkdir -p /root/.android/ && readlink -f $(which adb) >/root/.android/adb.5037
