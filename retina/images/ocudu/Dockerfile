# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION
FROM ${RETINA_REGISTRY_URI}/ocudu-base:$RETINA_VERSION AS ocudu-base
FROM ocudu-base AS ocudu-gnb

ARG RETINA_AGENT=ocudu-gnb
ENV RETINA_AGENT=$RETINA_AGENT

ENTRYPOINT ["/usr/local/bin/ocudu_entrypoint.sh"]