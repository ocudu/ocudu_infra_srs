# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.0"
    }
  }
  backend "http" {}
}

variable "infra_srs_path" { type = string }
variable "infra_srs_ref" { type = string }
variable "registry_auth" {
  type      = string
  sensitive = true
}
variable "retina_registry_uri" { type = string }
variable "retina_version" { type = string }
variable "gitlab_runner_token" {
  type      = string
  sensitive = true
}

provider "kubernetes" {} # reads KUBE_CONFIG_PATH env var set by CI

module "retina_cluster_setup" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/retina-cluster-setup?ref=${var.infra_srs_ref}"

  registry_auth              = var.registry_auth
  registry_secret_namespaces = ["infra", "retina"]
}

module "retina_cluster_definition" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/retina-cluster-definition?ref=${var.infra_srs_ref}"

  cluster_config_path = abspath("${path.module}/../retina_info.yml")
}
import {
  to = module.retina_cluster_definition.kubernetes_config_map_v1.retina_info
  id = "retina/retina-info"
}

module "retina_cronjobs_ocudu" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/retina-cronjobs?ref=${var.infra_srs_ref}"

  suffix              = "ocudu"
  namespace           = "infra"
  retina_registry_uri = var.retina_registry_uri
  retina_version      = var.retina_version
  gitlab_runner_token = var.gitlab_runner_token
  runners_file        = [abspath("${path.module}/../runners.yaml")]
  cronjobs = {
    "runner-manager" = {
      type        = "runner-manager"
      tolerations = [{ key = "purpose", operator = "Equal", value = "retina-e2e", effect = "NoSchedule" }]
    }
    "amarisoft-license" = {
      type        = "amarisoft-license"
      tolerations = [{ key = "purpose", operator = "Equal", value = "retina-e2e", effect = "NoSchedule" }]
    }
  }
}
