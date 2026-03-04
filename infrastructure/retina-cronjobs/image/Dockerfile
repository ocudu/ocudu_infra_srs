# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG RETINA_VERSION=""
ARG RETINA_REGISTRY_URI=""

FROM ${RETINA_REGISTRY_URI}/launcher:${RETINA_VERSION}

COPY amarisoft_license.py deletePods.sh gitlab_checker.py retina_runner.py reserve_resource.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/amarisoft_license.py /usr/local/bin/deletePods.sh /usr/local/bin/retina_runner.py /usr/local/bin/reserve_resource.sh

RUN pip install python-gitlab slack-sdk aiohttp && \
    apk add --no-cache jq

