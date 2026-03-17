#!/bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

set -e

# Generate env for launching tests in cluster (call it when you change retina repo and first time)
cd $RETINA_PATH/../e2e/retina_requests
python3 $RETINA_PATH/_scripts/generate_env.py --ocudu-path $OCUDU_PATH --amari-path $AMARISOFT_PATH

# Generate variables from retina code (call it when you change retina repo and first time)
cd $RETINA_PATH/_scripts
python3 generate_env.py --ocudu-path ${OCUDU_PATH} --amari-path ${AMARISOFT_PATH}

# Create testbed (call it when you change the profile and first time)
python3 generate_testbed.py --profile ${RETINA_PROFILE}

# Kill previous run if still there
docker compose --profile all down --volumes --remove-orphans >/dev/null 2>&1

# Set Trap for teardown
cleanup() {
    docker compose --profile all stop
    docker compose --profile all down --volumes --remove-orphans
    exit 0
}
trap cleanup INT TERM

# Run agents
docker compose --profile ${RETINA_PROFILE} up --detach
docker compose --profile ${RETINA_PROFILE} logs --follow --since 0s --timestamps
