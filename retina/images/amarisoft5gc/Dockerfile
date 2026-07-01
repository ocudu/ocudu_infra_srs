# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION

FROM ${RETINA_REGISTRY_URI}/wheelhouse:${RETINA_VERSION} AS wheelhouse

FROM ${RETINA_REGISTRY_URI}/agent:${AGENT_OS_VERSION} AS agent
FROM agent AS amarisoft_mme
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y --no-install-recommends iptables libsctp1 lksctp-tools iproute2 lksctp-tools \
    && apt-get autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="${PATH}:/opt/amarisoft/mme/"

ADD amarisoft_mme_entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/amarisoft_mme_entrypoint.sh
ENTRYPOINT ["/usr/local/bin/amarisoft_mme_entrypoint.sh"]

# Install retina
COPY --from=wheelhouse /src/wheelhouse /app/
RUN pip install --break-system-packages --no-index --find-links /app/ retina-agent
