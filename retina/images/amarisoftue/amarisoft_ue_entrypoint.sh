#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

set -e

wait_for_path() {
    local path="$1"
    local max_attempts="${2:-1800}"
    for _ in $(seq 1 "$max_attempts"); do
        [ -e "$path" ] && return 0
        echo "Waiting for ${path}..."
        sleep 1
    done
    echo "ERROR: Timed out waiting for ${path}" >&2
    return 1
}

# Setup Interfaces
(mkdir -p /dev/net && mknod /dev/net/tun c 10 200 >/dev/null 2>&1) || true

# Wait for amarisoft binaries
amarisoft_dir=/builds/amarisoft/
wait_for_path "$amarisoft_dir"/bin

# Install amarisoft binaries and pre-compiled uhd driver
amarisoft_tmp=$(mktemp -d)
cp -r "$amarisoft_dir"/bin/. "$amarisoft_tmp"/
"$amarisoft_tmp"/install.sh --default --no-srv --no-ht --no-all --ue --no-package --trx-no-upgrade --trx s72 /opt/amarisoft
mkdir -p /opt/amarisoft/trx_uhd && tar xzf "$amarisoft_tmp"/trx_uhd-*.tar.gz --to-stdout --wildcards "*/trx_uhd.so.tar.gz" | tar xz -C /opt/amarisoft/trx_uhd
ln -s /opt/amarisoft/trx_uhd/trx_uhd.so /opt/amarisoft/ue/trx_uhd.so
rm -rf "$amarisoft_tmp"

# Install ocudu zmq driver
if wait_for_path "$amarisoft_dir"/trx_ocudu.so 2; then
    cp "$amarisoft_dir"/trx_ocudu.so /opt/amarisoft/ue/
else
    echo "trx_ocudu.so not found, skipping (expected for non-zmq testbeds)"
fi

# Retina Agent
exec /usr/local/bin/agent.sh amarisoft-ue --maximum-workers 96 "$@"
