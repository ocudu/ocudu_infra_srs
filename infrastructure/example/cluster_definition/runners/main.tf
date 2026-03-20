# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

terraform {
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.0"
    }
  }
  backend "http" {}
}

variable "infra_srs_path" { type = string }
variable "infra_srs_ref" { type = string }
variable "gitlab_runner_token" {
  type      = string
  sensitive = true
}

provider "helm" {} # reads KUBE_CONFIG_PATH env var set by CI

module "gitlab_runners" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/gitlab-runner?ref=${var.infra_srs_ref}"

  runners_file        = [abspath("${path.module}/../runners.yaml")]
  cluster_type        = "ocudu"
  gitlab_runner_token = var.gitlab_runner_token
}
