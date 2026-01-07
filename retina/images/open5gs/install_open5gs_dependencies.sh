#! /bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


set -e

. /etc/os-release

# Workaround until repo is available for ubuntu 24.04
if [[ "$UBUNTU_CODENAME" == "noble" ]]; then
    UBUNTU_CODENAME=jammy
fi

# mongdb
DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends ca-certificates wget gnupg
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | apt-key add
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $UBUNTU_CODENAME/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends mongodb-org &&
    apt-get autoremove && apt-get clean

# open5g
DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    libtalloc-dev libmongoc-dev libyaml-dev libsctp-dev libnghttp2-dev \
    libmicrohttpd-dev libcurl4-gnutls-dev libtins-dev libidn11-dev \
    iptables netcat-openbsd &&
    apt-get autoremove && apt-get clean
