#!/bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

set -e
shopt -s nullglob

# Define or export the RETINA_AGENT variable
export RETINA_AGENT=${RETINA_AGENT:-ocudu-gnb}

if grep -q avx512 /proc/cpuinfo; then
    # If there are avx512 versions of dpdk libs -> Rename them as default ones
    echo "Renaming AVX512 DPDK libraries..."
    for dir in /opt/dpdk/*_avx512; do
        base_dir="${dir%_avx512}"
        if [ -d $base_dir ]; then
            echo "Skipping $dir -> $base_dir (already exists)"
            continue
        fi
        echo "$dir -> $base_dir"
        mv "$dir" "$base_dir"
        find /opt/dpdk -maxdepth 1 -type d -name "$(basename "$base_dir")_*" -exec rm -rf {} +;
    done
elif grep -q avx2 /proc/cpuinfo; then
    # If there are avx2 versions of dpdk libs -> Rename them as default ones
    echo "Renaming AVX2 DPDK libraries..."
    for dir in /opt/dpdk/*_avx2; do
        base_dir="${dir%_avx2}"
        if [ -d $base_dir ]; then
            echo "Skipping $dir -> $base_dir (already exists)"
            continue
        fi
        echo "$dir -> $base_dir"
        mv "$dir" "$base_dir"
        find /opt/dpdk -maxdepth 1 -type d -name "$(basename "$base_dir")_*" -exec rm -rf {} +;
    done
fi

exec /usr/local/bin/agent.sh "$RETINA_AGENT" "$@"