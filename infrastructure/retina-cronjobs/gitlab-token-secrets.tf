#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

resource "kubernetes_secret_v1" "gitlab_runner_token" {
  metadata {
    name      = "gitlabtoken-${var.suffix}"
    namespace = var.namespace
  }

  data = {
    GITLAB_TOKEN = var.gitlab_runner_token
  }

  type = "Opaque"
}
