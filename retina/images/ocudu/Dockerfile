# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG AGENT_OS_VERSION
ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION

ARG BUILDER_IMAGE

FROM ${RETINA_REGISTRY_URI}/wheelhouse:${RETINA_VERSION} AS wheelhouse

FROM $BUILDER_IMAGE AS builder

FROM ${RETINA_REGISTRY_URI}/agent:${AGENT_OS_VERSION} AS agent
FROM agent AS ocudu

RUN apt-get update && apt-get install -y --no-install-recommends llvm gdb \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/install_dependencies.sh /usr/local/bin/install_ocudu_dependencies.sh
COPY --from=builder /usr/local/bin/common.sh /usr/local/bin/common.sh
COPY --from=builder /opt/dpdk /opt/dpdk
COPY --from=builder /opt/uhd /opt/uhd
COPY --from=builder /opt/rohc /opt/rohc

RUN chmod -R 600 /opt/dpdk/*/lib/*-linux-gnu/ \
    && /usr/local/bin/install_ocudu_dependencies.sh run \
    && /usr/local/bin/install_ocudu_dependencies.sh extra \
    && apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer
ENV ASAN_OPTIONS=symbol_line=1
ENV TSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer
ENV RTSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer
ENV RTSAN_OPTIONS="halt_on_error=false:suppress_equal_stacks=true"

ADD ocudu_entrypoint.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/ocudu_entrypoint.sh"]

# Install retina
COPY --from=wheelhouse /src/wheelhouse /app/
RUN pip install --break-system-packages --no-index --find-links /app/ retina-agent
