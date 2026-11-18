#!/bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

set -e

AMARI_ARGS=()
if [[ -n "$AMARISOFT_PATH" ]]; then
    AMARI_ARGS=(--amari-path "$AMARISOFT_PATH")
fi

# Generate env for launching tests in cluster (call it when you change retina repo and first time)
cd $RETINA_PATH/../e2e/retina_requests
python3 $RETINA_PATH/_scripts/generate_env.py --ocudu-path $OCUDU_PATH "${AMARI_ARGS[@]}"

# Generate variables from retina code (call it when you change retina repo and first time)
cd $RETINA_PATH/_scripts
# Local retina version: hash of the image build inputs (see local_version.sh)
# - Docker builds the images only when the hash changes (Dockerfiles, entrypoints, dependencies, build args...)
# - Python code is shared with the containers, so changing it reuses the images
# - To build the images from scratch again, remove them (docker rmi / prune) or use --build flag in docker compose
RETINA_VERSION=$("$RETINA_PATH/_scripts/local_version.sh")
RETINA_VERSION=${RETINA_VERSION} python3 generate_env.py --ocudu-path ${OCUDU_PATH} "${AMARI_ARGS[@]}"

# Create testbed (call it when you change the profile and first time)
python3 generate_testbed.py --profile ${RETINA_PROFILE}

# Kill previous run if still there
docker compose --profile ${RETINA_PROFILE} down --volumes --remove-orphans

# Set Trap for teardown
cleanup() {
    docker compose --profile ${RETINA_PROFILE} stop
    docker compose --profile ${RETINA_PROFILE} down --volumes --remove-orphans
    exit 0
}
trap cleanup INT TERM

if ! docker buildx version >/dev/null 2>&1; then
    echo "Error: docker buildx is not installed. Install it using your repository manager or as a docker plugin. Check https://github.com/docker/buildx#installing" >&2
    exit 1
fi

# Run agents
docker compose --profile ${RETINA_PROFILE} up "$@" --detach
docker compose --profile ${RETINA_PROFILE} logs --follow --since 0s --timestamps
