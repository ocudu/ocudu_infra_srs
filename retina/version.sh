#!/bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

# Prints the RETINA_VERSION to stdout.
# Format: YYYY.MM.DD.{decimal_tree_hash}
#
# Both values are derived from git, so the version is deterministic across
# machines, operating systems, and forks with identical retina/ content.
#
# Usage: sh version.sh

REPO_ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
DATE=$(git -C "$REPO_ROOT" log -1 --format="%ad" --date=format:"%Y.%m.%d" -- retina/)
TREE_HASH=$(git -C "$REPO_ROOT" rev-parse HEAD:retina/)
HASH8=$(printf '%.8s' "$TREE_HASH")
echo "${DATE}.$(printf '%d' "0x${HASH8}")"
