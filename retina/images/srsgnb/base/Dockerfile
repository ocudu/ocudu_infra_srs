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

ARG BUILDER_IMAGE

FROM $BUILDER_IMAGE AS builder

FROM ${CI_REGISTRY_IMAGE}/retina/agent-ubuntu-$AGENT_OS_VERSION:$RETINA_VERSION AS agent
FROM agent AS gnb-base

COPY --from=builder /usr/local/bin/install_dependencies.sh /usr/local/bin/install_srsran_dependencies.sh
COPY --from=builder /opt/dpdk /opt/dpdk
COPY --from=builder /opt/uhd /opt/uhd
COPY --from=builder /opt/rohc /opt/rohc

RUN chmod -R 600 /opt/dpdk/*/lib/*-linux-gnu/ \
    && /usr/local/bin/install_srsran_dependencies.sh \
    # llvm-symbolizer required for ASAN/TSAN 
    && apt-get install -y --no-install-recommends llvm gdb \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN export ASAN_OPTIONS=symbol_line=1

RUN uhd_images_downloader -t b2xx_
RUN uhd_images_downloader -t n310
RUN uhd_images_downloader -t x3xx_

ADD srsgnb_entrypoint.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/srsgnb_entrypoint.sh"]
