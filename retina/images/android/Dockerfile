# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION=24.04
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION

FROM ${RETINA_REGISTRY_URI}/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS android

ADD android_setup.sh /usr/local/bin/
ADD Android_UE_Controller_CLI.py /opt/ue_controller/
ADD Android_UE_Controller.py /opt/ue_controller/

RUN /usr/local/bin/android_setup.sh \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    ln -s /opt/ue_controller/Android_UE_Controller_CLI.py /usr/local/bin/ue_controller

ENTRYPOINT ["/usr/local/bin/agent.sh", "android"]