#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ARG TERRAFORM_VERSION
FROM hashicorp/terraform:$TERRAFORM_VERSION

RUN apk add --no-cache \
      python3 \
      py3-pip \
      jq \
      py3-yaml \
      bash && \
    pip3 install --break-system-packages --root-user-action=ignore requests