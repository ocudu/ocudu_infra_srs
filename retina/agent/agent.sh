#! /bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI


retina_ports_cmd="$@"
if [[ -n $RETINA_PORTS ]]; then
    retina_ports_cmd="$retina_ports_cmd --server-ports $RETINA_PORTS"
fi

exec python3 -m retina.agent $retina_ports_cmd $RETINA_AGENT_ARGS
