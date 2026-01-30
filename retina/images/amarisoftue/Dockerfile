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

# Add amarisoftue bins and libs
ADD amarisoft/${AMARISOFT_VERSION}/lteue-linux-${AMARISOFT_VERSION}.tar.gz /opt/
ADD amarisoft/${AMARISOFT_VERSION}/libs/**/*.so* /opt/lteue-linux-${AMARISOFT_VERSION}/
ADD amarisoft/${AMARISOFT_VERSION}/trx_*-${AMARISOFT_VERSION}.tar.gz /tmp
RUN cp /tmp/trx_*-${AMARISOFT_VERSION}/trx_*.so /opt/lteue-linux-${AMARISOFT_VERSION}/

# Compile trx_uhd.so
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    uhd-host libuhd-dev make build-essential libboost-program-options-dev \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*
# Install script only supports amd (requires sse2)
RUN if [ "$(uname -m)" = "x86_64" ]; then \
    sed -i 's/Noble/24.04 Noble/g' /etc/lsb-release && \
    /tmp/trx_uhd*${AMARISOFT_VERSION}/install.sh /opt/lteue-linux-${AMARISOFT_VERSION}/ ue > /opt/lteue-linux-${AMARISOFT_VERSION}/uhd_install.log; \
    fi

# Clean
RUN mv /opt/lteue-linux-${AMARISOFT_VERSION} /opt/lteue
RUN rm -Rf /opt/lteue/doc

# Fix ssl 1.1
RUN echo "deb http://security.ubuntu.com/ubuntu focal-security main" >> /etc/apt/sources.list.d/focal-security.list && \
    echo "deb http://ports.ubuntu.com/ubuntu-ports focal-security main" >> /etc/apt/sources.list.d/focal-security.list && \
    (apt-get update || true) && apt-get install libssl1.1
RUN mv /usr/lib/*-linux-gnu/libcrypto.so.1.1 /opt/lteue/libcrypto.so.1.1 && \
    mv /usr/lib/*-linux-gnu/libssl.so.1.1    /opt/lteue/libssl.so.1.1
# RUN [ ! -d /opt/lteue/libcrypto.so.1.1 ] && ln -sf /opt/lteue/libcrypto.so.1 /opt/lteue/libcrypto.so.1.1
# RUN [ ! -d /opt/lteue/libssl.so.1.1 ] && ln -sf /opt/lteue/libssl.so.1 /opt/lteue/libssl.so.1.1

FROM ${RETINA_REGISTRY_URI}/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS amarisoftue
COPY --from=binary_setup /opt/lteue /opt/lteue
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    uhd-host libuhd-dev libzmq3-dev \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*
ENV PATH="${PATH}:/opt/lteue"

RUN uhd_images_downloader -t b2xx_
RUN uhd_images_downloader -t n310
RUN uhd_images_downloader -t x3xx_

ADD amarisoft_ue_entrypoint.sh amarisoft_ue_setup.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/amarisoft_ue_entrypoint.sh"]
