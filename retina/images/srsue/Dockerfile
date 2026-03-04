# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION=24.04
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION
FROM ubuntu:${AGENT_OS_VERSION} AS builder

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN DEBIAN_FRONTEND=noninteractive TZ=Europe/Madrid \ 
  apt-get update && apt-get install -y --no-install-recommends \
  build-essential cmake libfftw3-dev libmbedtls-dev libboost-program-options-dev libconfig++-dev libsctp-dev ninja-build valgrind rapidjson-dev \
  libboost-all-dev libsctp-dev uhd-host libuhd-dev libzmq3-dev libsoapysdr-dev \
  git apt-transport-https ca-certificates \
  && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG REPO_URL=https://github.com/srsran/srsRAN_4G.git
ARG REPO_BRANCH=release_23_11
RUN git clone --depth 1 --branch $REPO_BRANCH $REPO_URL srsran\
  && cd srsran \
  && mkdir -p build \
  && cd build \
  && cmake -DENABLE_WERROR=False -DENABLE_SRSUE=True -DENABLE_SRSENB=True -DENABLE_SRSEPC=False -DENABLE_GUI=False -DRF_FOUND=True -DAUTO_DETECT_ISA=False -DDISABLE_SIMD=True -DGCC_ARCH="x86-64-v3" -GNinja .. \
  && ninja \
  && ninja install

RUN ldconfig

FROM ${RETINA_REGISTRY_URI}/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS srsue
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/include/srsran /usr/local/include/srsran
COPY --from=builder /usr/local/lib /usr/local/lib

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN DEBIAN_FRONTEND=noninteractive TZ=Europe/Madrid \ 
  apt-get update && apt-get install -y --no-install-recommends \
  libboost-program-options-dev libmbedcrypto7 libconfig++-dev libsctp-dev libfftw3-dev \
  uhd-host libuhd-dev libzmq3-dev libsoapysdr-dev \
  && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN uhd_images_downloader -t b2xx_
RUN uhd_images_downloader -t n310
RUN uhd_images_downloader -t x3xx_

ADD srsue_entrypoint.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/srsue_entrypoint.sh"]