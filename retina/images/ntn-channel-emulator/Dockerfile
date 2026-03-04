# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

# syntax=docker/dockerfile:1.2

ARG AGENT_OS_VERSION=24.04
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION
FROM ${RETINA_REGISTRY_URI}/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION as agent
FROM agent AS ntn-channel-emulator

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get upgrade --yes && \
    DEBIAN_FRONTEND=noninteractive apt-get install --yes \
        python3 \
        python3-pip && \
    apt-get clean

# Install the required Python packages using pip
RUN pip3 config set global.break-system-packages true
RUN pip3 install  --ignore-installed --no-cache-dir pyzmq skyfield numpy numba asn1tools pyyaml

COPY ntn-channel-emulator /ntn-channel-emulator

ENTRYPOINT ["/usr/local/bin/agent.sh", "ntn-channel-emulator"]
