#!/bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

# Prints the RETINA_VERSION for local images: a hash of the image build inputs in retina/.
# Python sources mounted into the containers are excluded, so changing them reuses the images.
#
# Usage: local_version.sh

set -eu

RETINA_DIR="$(cd "$(dirname "$0")/.." && pwd)"

HASH8=$(
    git -C "$RETINA_DIR" ls-files -z --cached --others --exclude-standard -- . \
        ':(exclude)*/src/retina/**' \
        ':(exclude,glob)**/tests/**' \
        ':(exclude)_scripts/**' \
        ':(exclude)_docs/**' \
        ':(exclude,glob)**/*.md' |
        sort -z |
        (cd "$RETINA_DIR" && xargs -0 -r sha1sum -- 2>/dev/null || true) |
        sha1sum | cut -c1-8
)
# Must be a valid Python package version (PEP 440) and Docker tag. 0.0.0 avoids clashing with CI versions.
echo "0.0.0.$((16#$HASH8))"
