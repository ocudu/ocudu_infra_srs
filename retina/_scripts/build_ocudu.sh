#!/bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

set -e

# Profile with the builders to run. Available: builders (default), builders-rt
PROFILE=${1:-builders}

cd $RETINA_PATH/_scripts
python3 generate_env.py --ocudu-path ${OCUDU_PATH} --amari-path ${AMARISOFT_PATH}
docker compose --profile ${PROFILE} up

# Alternatively, you can run the build container with custom flags:
# docker compose run --rm ocudu-builder \
#   builder.sh -b build_retina -m "gnb" -c clang \
#   -DBUILD_TESTING=False -DCMAKE_BUILD_TYPE=Debug -DASSERT_LEVEL=PARANOID \
#   -DENABLE_TSAN=True -DEXIT_TIMEOUT=120 \
#   /builds/ocudu/ocudu
