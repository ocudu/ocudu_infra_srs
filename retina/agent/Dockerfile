# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION

#################
# Iperf Builder #
#################
FROM ubuntu:${AGENT_OS_VERSION} AS iperf_builder
ARG IPERF_VERSION=3.14
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/esnet/iperf.git -b $IPERF_VERSION
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    make libtool m4 automake autoconf \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN cd iperf && \
    ./bootstrap.sh && \
    ./configure --prefix=/opt/iperf && \
    make && \
    make install

######################
# Final docker image #
######################
FROM ubuntu:${AGENT_OS_VERSION}

# OS dependencies + tshark from the Wireshark stable PPA
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository -y ppa:wireshark-dev/stable \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    net-tools netcat-openbsd iproute2 iputils-ping \
    htop nano \
    tshark \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy iperf
ENV PATH="${PATH}:/opt/iperf/bin"
COPY --from=iperf_builder /opt/iperf /opt/iperf

# Retina Setup
ENV PYTHONBUFFERED=1
WORKDIR /var/log/retina
# export grpc default port
EXPOSE 50051
ADD agent/agent.sh /usr/local/bin/
