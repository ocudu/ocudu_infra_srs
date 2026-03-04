#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


set -e

# Set up TUN device inside the container
(mkdir -p /dev/net && mknod /dev/net/tun c 10 200 >/dev/null 2>&1) || true
