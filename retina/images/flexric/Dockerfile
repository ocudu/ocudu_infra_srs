# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION=24.04
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION
FROM ubuntu:${AGENT_OS_VERSION} AS builder

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
       swig \
       build-essential \
       libsctp-dev \
       git \
       wget \
       tar \
       m4 \
       automake \
       libtool \
       python3 \
       cmake \
       cmake-curses-gui \
       bison \
       flex \
       gdb \
       libpcre2-dev \
       python3-dev \
       python3-pip \
       pkg-config \
       libconfig-dev \
       libconfig++-dev \
       gcc-12 && \
    apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*


ARG REPO_URL=https://gitlab.eurecom.fr/mosaic5g/flexric.git
ARG REPO_BRANCH=br-flexric

RUN git clone --depth 1 --branch $REPO_BRANCH $REPO_URL /flexric
WORKDIR /flexric

# Patch PRB-quota Control xApp
COPY ./xapps-fix-e2sm-rc-prb-quota-control-xapp.patch .
RUN git apply ./xapps-fix-e2sm-rc-prb-quota-control-xapp.patch

RUN mkdir build && \
    cd build && \
    cmake -DCMAKE_C_COMPILER=gcc-12 -DKPM_VERSION=KPM_V3_00 -DXAPP_DB=NONE_XAPP .. && make -j8 && make install

RUN ldconfig

FROM ${RETINA_REGISTRY_URI}/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS flexric
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/local/etc/flexric/ /usr/local/etc/flexric/
COPY --from=builder /lib/x86_64-linux-gnu/libsctp.so.1 /lib/x86_64-linux-gnu/libsctp.so.1
COPY --from=builder /lib/x86_64-linux-gnu/libconfig.so.9 /lib/x86_64-linux-gnu/libconfig.so.9
COPY --from=builder /lib/x86_64-linux-gnu/libc.so.6 /lib/x86_64-linux-gnu/libc.so.6
COPY --from=builder /flexric /flexric

WORKDIR /var/log/retina

ENTRYPOINT ["/usr/local/bin/agent.sh", "flexric-ric"]
