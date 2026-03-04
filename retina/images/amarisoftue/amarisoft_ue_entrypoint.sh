#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


set -e

. amarisoft_ue_setup.sh

# Retina Agent
exec /usr/local/bin/agent.sh amarisoft-ue --maximum-workers 96 "$@"