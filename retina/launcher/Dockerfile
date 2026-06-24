# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG PYTHON_VERSION=3.12
ARG OS=alpine
FROM python:${PYTHON_VERSION}-${OS} AS builder
ENV PYTHONBUFFERED=1

# OS deps to build python libs
RUN apk add build-base linux-headers libffi-dev

# Install kubectl
WORKDIR /tmp
ARG KUBECTL_VERSION=v1.36.1
RUN apk add --no-cache curl tar \
    && curl -LO "https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl" \
    && curl -LO "https://dl.k8s.io/$KUBECTL_VERSION/bin/linux/amd64/kubectl.sha256" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm -Rf /tmp/*

# Install auxiliar tools
RUN apk add --no-cache git yq coreutils zip sshpass openssh-client
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
