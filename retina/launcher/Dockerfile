#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ARG PYTHON_VERSION=3.12
ARG OS=alpine
FROM python:${PYTHON_VERSION}-${OS} AS builder
ARG PIP_EXTRA_INDEX_URL=""
ENV PYTHONBUFFERED=1

# OS deps to build python libs
RUN apk add build-base linux-headers libffi-dev

# Add the folder
ADD . /src

ARG RETINA_VERSION
RUN pip install /src/viavi /src/protocol /src/client /src/orchestrator /src/launcher

# Install kubectl
WORKDIR /tmp
ARG KUBECTL_VERSION=v1.26.5
RUN apk add --no-cache curl tar \
    && curl -LO "https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl" \
    && curl -LO "https://dl.k8s.io/$KUBECTL_VERSION/bin/linux/amd64/kubectl.sha256" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm -Rf /tmp/*

# Install kubeval
RUN curl -L "https://github.com/instrumenta/kubeval/releases/latest/download/kubeval-linux-amd64.tar.gz" -o kubeval.tar.gz \
    && tar xf kubeval.tar.gz \
    && mv kubeval /usr/local/bin/kubeval \
    && rm kubeval.tar.gz

# Install auxiliar tools
RUN apk add --no-cache git git-lfs yq coreutils zip sshpass openssh-client
RUN apk add py-spy --update-cache --repository http://dl-3.alpinelinux.org/alpine/edge/testing/ --allow-untrusted

ARG INFLUX_VERSION=2.7.5
RUN cd /tmp && mkdir influxdb2-client-${INFLUX_VERSION}-linux-amd64 && \
    wget https://dl.influxdata.com/influxdb/releases/influxdb2-client-${INFLUX_VERSION}-linux-amd64.tar.gz && \
    tar xvzf influxdb2-client-${INFLUX_VERSION}-linux-amd64.tar.gz -C influxdb2-client-${INFLUX_VERSION}-linux-amd64 && \
    cp influxdb2-client-${INFLUX_VERSION}-linux-amd64/influx /usr/local/bin/ && \
    rm -Rf influxdb2-client-${INFLUX_VERSION}-linux-amd64*

WORKDIR /workdir

ENTRYPOINT ["/bin/sh"]
