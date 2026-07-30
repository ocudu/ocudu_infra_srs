# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION

FROM ${RETINA_REGISTRY_URI}/wheelhouse:${RETINA_VERSION} AS wheelhouse

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
RUN git clone --depth 1 --branch $REPO_BRANCH $REPO_URL srsran

# srsRAN_4G requests Boost COMPONENTS system, which Ubuntu 26.04 no longer
# provides a CMake config for. See boost-system-shim/boost_system-config.cmake.
COPY ./boost-system-shim /opt/boost-system-shim

RUN cd srsran \
  && mkdir -p build \
  && cd build \
  && cmake -DENABLE_WERROR=False -DENABLE_SRSUE=True -DENABLE_SRSENB=True -DENABLE_SRSEPC=False -DENABLE_GUI=False -DRF_FOUND=True -DAUTO_DETECT_ISA=False -DDISABLE_SIMD=True -DGCC_ARCH="x86-64-v3" -Dboost_system_DIR=/opt/boost-system-shim -GNinja .. \
  && ninja \
  && ninja install

RUN ldconfig

FROM ${RETINA_REGISTRY_URI}/agent:${AGENT_OS_VERSION} AS agent
FROM agent AS srsue
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/include/srsran /usr/local/include/srsran
COPY --from=builder /usr/local/lib /usr/local/lib

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN DEBIAN_FRONTEND=noninteractive TZ=Europe/Madrid \
  apt-get update && apt-get install -y --no-install-recommends \
  libboost-program-options-dev libmbedtls-dev libconfig++-dev libsctp-dev libfftw3-dev \
  uhd-host libuhd-dev libzmq3-dev libsoapysdr-dev \
  && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

ADD srsue_entrypoint.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/srsue_entrypoint.sh"]

# Install retina
COPY --from=wheelhouse /src/wheelhouse /app/
RUN pip install --break-system-packages --no-index --find-links /app/ retina-agent
