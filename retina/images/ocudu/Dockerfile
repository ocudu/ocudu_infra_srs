#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ARG RETINA_REGISTRY_URI
ARG RETINA_VERSION
FROM ${RETINA_REGISTRY_URI}/ocudu-base:$RETINA_VERSION AS ocudu-base
FROM ocudu-base AS ocudu-gnb

ARG RETINA_AGENT=ocudu-gnb
ENV RETINA_AGENT=$RETINA_AGENT

ENTRYPOINT ["/usr/local/bin/ocudu_entrypoint.sh"]