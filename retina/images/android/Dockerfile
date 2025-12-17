#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ARG AGENT_OS_VERSION=24.04
ARG CI_REGISTRY_IMAGE
ARG RETINA_VERSION

FROM ${CI_REGISTRY_IMAGE}/retina/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS android

ADD android_setup.sh /usr/local/bin/
ADD Android_UE_Controller_CLI.py /opt/ue_controller/
ADD Android_UE_Controller.py /opt/ue_controller/

RUN /usr/local/bin/android_setup.sh \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    ln -s /opt/ue_controller/Android_UE_Controller_CLI.py /usr/local/bin/ue_controller

ENTRYPOINT ["/usr/local/bin/agent.sh", "android"]