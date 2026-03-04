# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

locals {
  # Read the token file from private repo's cluster_definition/secrets/ directory
  # Path from CI workspace: infrastructure/retina-cronjobs/tf/ -> ../../../cluster_definition/secrets/
  token_file_path = "${path.module}/../../../cluster_definition/secrets/gitlab-tokens-${var.organization_name}.yaml"
  token_file      = yamldecode(file(local.token_file_path))
}

# Create GitLab runner token secret for runner-manager
resource "kubernetes_secret_v1" "gitlab_runner_token" {
  metadata {
    name      = "gitlabtoken-${var.organization_name}"
    namespace = var.namespace
  }

  data = {
    GITLAB_TOKEN = local.token_file.gitlab_runner_token
  }

  type = "Opaque"
}
