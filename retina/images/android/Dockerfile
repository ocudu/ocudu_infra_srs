# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION

FROM ${RETINA_REGISTRY_URI}/wheelhouse:${RETINA_VERSION} AS wheelhouse

FROM ${RETINA_REGISTRY_URI}/agent:${AGENT_OS_VERSION} AS agent
FROM agent AS android

ADD android_setup.sh /usr/local/bin/
ADD Android_UE_Controller_CLI.py /opt/ue_controller/
ADD Android_UE_Controller.py /opt/ue_controller/

RUN /usr/local/bin/android_setup.sh \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    ln -s /opt/ue_controller/Android_UE_Controller_CLI.py /usr/local/bin/ue_controller

ENTRYPOINT ["/usr/local/bin/agent.sh", "android"]

# Install retina
COPY --from=wheelhouse /src/wheelhouse /app/
RUN pip install --break-system-packages --no-index --find-links /app/ retina-agent
