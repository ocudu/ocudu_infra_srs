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

FROM ubuntu:$AGENT_OS_VERSION AS binary_setup
ARG AMARISOFT_VERSION

# Add amarisoft_mme bins and libs
ADD amarisoft/${AMARISOFT_VERSION}/ltemme-linux-${AMARISOFT_VERSION}.tar.gz /opt/
ADD amarisoft/${AMARISOFT_VERSION}/libs/**/*.so* /opt/ltemme-linux-${AMARISOFT_VERSION}/
RUN mv /opt/ltemme-linux-${AMARISOFT_VERSION} /opt/ltemme

FROM ${RETINA_REGISTRY_URI}/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS amarisoft_mme
COPY --from=binary_setup /opt/ltemme /opt/ltemme
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y --no-install-recommends iptables libsctp1 lksctp-tools \
    && apt-get autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="${PATH}:/opt/ltemme"

ADD amarisoft_mme_entrypoint.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/amarisoft_mme_entrypoint.sh"]
