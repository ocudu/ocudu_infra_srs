#! /bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


retina_ports_cmd="$@"
if [[ -n $RETINA_PORTS ]]; then
    retina_ports_cmd="$retina_ports_cmd --server-ports $RETINA_PORTS"
fi

exec python3 -m retina.agent $retina_ports_cmd $RETINA_AGENT_ARGS
