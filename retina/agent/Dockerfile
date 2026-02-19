#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ARG AGENT_OS_VERSION=24.04

#################
# Iperf Builder #
#################
FROM ubuntu:$AGENT_OS_VERSION AS iperf_builder
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

#################
# Agent Builder #
#################
FROM ubuntu:$AGENT_OS_VERSION AS builder

# OS dependencies
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev python3-pip \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

# Add the folder
ADD . /src
WORKDIR /src

# Build wheels and save dependencies
ARG RETINA_VERSION
RUN python3 -m pip wheel -w /src/wheelhouse protocol/ agent/

######################
# Final docker image #
######################
FROM ubuntu:$AGENT_OS_VERSION
ARG PIP_EXTRA_INDEX_URL=""

# Copy wheels
COPY --from=builder /src/wheelhouse /app/
COPY --from=iperf_builder /opt/iperf /opt/iperf

ENV PYTHONBUFFERED=1
ENV PATH="${PATH}:/opt/iperf/bin"

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

# Install the generated wheels
RUN python3 -m pip install --break-system-packages --ignore-installed /app/*.whl py-spy

WORKDIR /var/log/retina

# export grpc default port
EXPOSE 50051

ADD agent/agent.sh /usr/local/bin/

ENTRYPOINT ["/usr/local/bin/agent.sh", "ocudu-gnb"]
