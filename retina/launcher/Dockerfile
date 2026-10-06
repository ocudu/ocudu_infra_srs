# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG PYTHON_VERSION=3.14
ARG OS=alpine
ARG KUBECTL_VERSION=v1.36.1

# BuildKit gets this image, so the build container does not resolve dl.k8s.io
FROM registry.k8s.io/kubectl:${KUBECTL_VERSION} AS kubectl

FROM python:${PYTHON_VERSION}-${OS} AS builder
ENV PYTHONBUFFERED=1

# OS deps to build python libs
RUN apk add build-base linux-headers libffi-dev

# Install kubectl
COPY --from=kubectl /bin/kubectl /usr/local/bin/kubectl

# Install auxiliar tools
RUN apk add --no-cache curl tar git yq coreutils zip sshpass openssh-client wget
RUN apk add py-spy --update-cache --repository http://dl-3.alpinelinux.org/alpine/edge/testing/ --allow-untrusted

# Install Python packages
ARG RETINA_VERSION
ARG PIP_EXTRA_INDEX_URL=""
COPY viavi/ /src/viavi/
COPY protocol/ /src/protocol/
COPY client/ /src/client/
COPY orchestrator/ /src/orchestrator/
COPY launcher/ /src/launcher/
RUN pip install /src/viavi /src/protocol /src/client /src/orchestrator /src/launcher

WORKDIR /workdir

ENTRYPOINT ["/bin/sh"]
