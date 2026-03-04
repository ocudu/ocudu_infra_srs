# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ARG TERRAFORM_VERSION
FROM hashicorp/terraform:$TERRAFORM_VERSION

RUN apk add --no-cache \
      python3 \
      py3-pip \
      jq \
      py3-yaml \
      bash && \
    pip3 install --break-system-packages --root-user-action=ignore requests