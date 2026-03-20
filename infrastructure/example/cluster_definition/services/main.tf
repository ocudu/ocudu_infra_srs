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

provider "helm" {} # reads KUBE_CONFIG_PATH env var set by CI

module "tuned" {
  source        = "git::https://${var.infra_srs_path}.git//infrastructure/tuned?ref=${var.infra_srs_ref}"
  services_file = [abspath("${path.module}/../services.yaml")]
}

module "linuxptp" {
  source        = "git::https://${var.infra_srs_path}.git//infrastructure/linuxptp?ref=${var.infra_srs_ref}"
  services_file = [abspath("${path.module}/../services.yaml")]
}
