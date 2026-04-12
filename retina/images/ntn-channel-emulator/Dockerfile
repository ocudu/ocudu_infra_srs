# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION

FROM ${RETINA_REGISTRY_URI}/wheelhouse:${RETINA_VERSION} AS wheelhouse

FROM ${RETINA_REGISTRY_URI}/agent:${AGENT_OS_VERSION} as agent
FROM agent AS ntn-channel-emulator

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip && \
    apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install the required Python packages using pip
RUN pip3 config set global.break-system-packages true
RUN pip3 install  --ignore-installed --no-cache-dir pyzmq skyfield numpy numba asn1tools pyyaml

COPY ntn-channel-emulator /ntn-channel-emulator

ENTRYPOINT ["/usr/local/bin/agent.sh", "ntn-channel-emulator"]

# Install retina
COPY --from=wheelhouse /src/wheelhouse /app/
RUN pip install --break-system-packages --no-index --find-links /app/ retina-agent
