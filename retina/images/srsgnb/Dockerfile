#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ARG CI_REGISTRY_IMAGE
ARG RETINA_VERSION
FROM ${CI_REGISTRY_IMAGE}/retina/srsgnb-base:$RETINA_VERSION AS gnb-base
FROM gnb-base AS srsgnb

ARG RETINA_AGENT=srs-gnb
ENV RETINA_AGENT=$RETINA_AGENT

ENTRYPOINT ["/usr/local/bin/srsgnb_entrypoint.sh"]
