#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


# Set up TUN device inside the container
mkdir -p /dev/net && mknod /dev/net/tun c 10 200 >/dev/null 2>&1 || true

# Retina Agent
exec /usr/local/bin/agent.sh srs-ue "$@"