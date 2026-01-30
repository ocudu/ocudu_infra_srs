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
FROM ubuntu:${AGENT_OS_VERSION} AS builder

ENV PYTHONBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive 
ENV TZ=Europe/Madrid
ENV REPO_URL=https://github.com/open5gs/open5gs

RUN apt-get update \
    && apt install -y software-properties-common \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN cp /usr/bin/true /usr/sbin/telinit && \
    apt-get update \
    && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    ninja-build \
    build-essential \
    flex \
    bison \
    git \
    libsctp-dev \
    libgnutls28-dev \
    libgcrypt-dev \
    libssl-dev \
    libidn11-dev \
    libmongoc-dev \
    libbson-dev \
    libyaml-dev \
    libnghttp2-dev \
    libmicrohttpd-dev \
    libcurl4-gnutls-dev \
    libnghttp2-dev \
    libtins-dev \
    meson \
    gettext \
    gdb \
    iproute2 \
    iptables \
    iputils-ping \
    netcat-openbsd \
    iperf3 \
    libtalloc-dev \
    cmake \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG OPEN5GS_VERSION=v2.7.0

# open5gs
ADD retina.patch /tmp/retina.patch
RUN git clone --depth 1 --branch $OPEN5GS_VERSION $REPO_URL open5gs\
    && cd open5gs \
    && meson build --prefix=`pwd`/install \
    && ninja -C build \
    && git apply /tmp/retina.patch \
    && cd build \
    && ninja install

FROM ${RETINA_REGISTRY_URI}/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS open5gs
COPY --from=builder /open5gs/install/bin /usr/local/bin
COPY --from=builder /open5gs/build/tests/app/5gc /usr/local/bin/5gc
COPY --from=builder /open5gs/build/configs /open5gs/configs
COPY --from=builder /open5gs/install/lib/ /tmp/libs/
COPY --from=builder /open5gs/install/etc /usr/local/etc
COPY --from=builder /open5gs/misc/db/python /open5gs/misc/db/python
COPY --from=builder /open5gs/webui /open5gs/webui

RUN mv /tmp/libs/*-linux-gnu/* /usr/local/lib/
ADD install_open5gs_dependencies.sh /usr/local/bin/
RUN /usr/local/bin/install_open5gs_dependencies.sh \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

ADD open5gs_setup.sh open5gs_entrypoint.sh open5gs_teardown.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/open5gs_entrypoint.sh"]
