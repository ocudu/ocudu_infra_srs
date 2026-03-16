# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

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
