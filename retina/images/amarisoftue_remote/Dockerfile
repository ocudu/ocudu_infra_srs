#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ARG AGENT_OS_VERSION=24.04
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION

FROM ${RETINA_REGISTRY_URI}/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS amarisoftue-remote
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    ssh sshpass \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/usr/local/bin/agent.sh", "amarisoft-ue-remote", "--maximum-workers", "96"]
