#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ARG RETINA_VERSION=""
ARG CR_REGISTRY_URI=""

FROM ${CR_REGISTRY_URI}/ocudu_infra_srs/retina/launcher:${RETINA_VERSION}

COPY amarisoft_license.py deletePods.sh gitlab_checker.py retina_runner.py reserve_resource.sh /usr/local/bin/

RUN pip install python-gitlab slack-sdk aiohttp && \
    apk add --no-cache jq

