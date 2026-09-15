#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


set -e

. /etc/os-release

# mongdb
MONGODB_VERSION=8.0
MONGODB_FALLBACK_CODENAME=noble

DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends ca-certificates wget gnupg

MONGODB_ARCH="$(dpkg --print-architecture)"
MONGODB_CODENAME="$UBUNTU_CODENAME"
if ! wget -qO- "https://repo.mongodb.org/apt/ubuntu/dists/$MONGODB_CODENAME/mongodb-org/$MONGODB_VERSION/multiverse/binary-$MONGODB_ARCH/Packages" | grep -q "^Package: mongodb-org-server$"; then
    echo "MongoDB $MONGODB_VERSION has no mongodb-org-server package for '$UBUNTU_CODENAME' ($MONGODB_ARCH), falling back to '$MONGODB_FALLBACK_CODENAME'"
    MONGODB_CODENAME="$MONGODB_FALLBACK_CODENAME"
fi

install -d -m 0755 /etc/apt/keyrings
wget -qO "/etc/apt/keyrings/mongodb-server-$MONGODB_VERSION.asc" "https://www.mongodb.org/static/pgp/server-$MONGODB_VERSION.asc"
chmod 0644 "/etc/apt/keyrings/mongodb-server-$MONGODB_VERSION.asc"
echo "deb [ arch=amd64,arm64 signed-by=/etc/apt/keyrings/mongodb-server-$MONGODB_VERSION.asc ] https://repo.mongodb.org/apt/ubuntu $MONGODB_CODENAME/mongodb-org/$MONGODB_VERSION multiverse" > "/etc/apt/sources.list.d/mongodb-org-$MONGODB_VERSION.list"

DEBIAN_FRONTEND=noninteractive apt-get update
apt-get install -y --no-install-recommends \
    mongodb-org-server mongodb-org-shell mongodb-mongosh
apt-get autoremove
apt-get clean

# open5g
DEBIAN_FRONTEND=noninteractive apt-get update
apt-get install -y --no-install-recommends \
    libtalloc-dev libmongoc-dev libyaml-dev libsctp-dev libnghttp2-dev \
    libmicrohttpd-dev libcurl4-gnutls-dev libtins-dev libidn11-dev \
    iptables netcat-openbsd
apt-get autoremove
apt-get clean
