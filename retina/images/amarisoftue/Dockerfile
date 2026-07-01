# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION

FROM ${RETINA_REGISTRY_URI}/wheelhouse:${RETINA_VERSION} AS wheelhouse

FROM ${RETINA_REGISTRY_URI}/agent:${AGENT_OS_VERSION} AS agent
FROM agent AS amarisoftue
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    uhd-host libuhd-dev libzmq3-dev \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*
ENV PATH="${PATH}:/opt/amarisoft/ue"

ADD amarisoft_ue_entrypoint.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/amarisoft_ue_entrypoint.sh"]

# Install retina
COPY --from=wheelhouse /src/wheelhouse /app/
RUN pip install --break-system-packages --no-index --find-links /app/ retina-agent
