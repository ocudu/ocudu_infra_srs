#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


set -e

. /etc/os-release

# mongdb
DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends ca-certificates wget gnupg
wget -qO - https://www.mongodb.org/static/pgp/server-8.0.asc | apt-key add
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $UBUNTU_CODENAME/mongodb-org/8.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-8.0.list
DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    mongodb-org-server mongodb-org-shell mongodb-mongosh &&
    apt-get autoremove && apt-get clean

# open5g
DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    libtalloc-dev libmongoc-dev libyaml-dev libsctp-dev libnghttp2-dev \
    libmicrohttpd-dev libcurl4-gnutls-dev libtins-dev libidn11-dev \
    iptables netcat-openbsd &&
    apt-get autoremove && apt-get clean
