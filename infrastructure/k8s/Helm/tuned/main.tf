# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

terraform {
  backend "http" {}

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "2.13.2"
    }
  }
}

variable "tuned_version" {
  type    = string
  default = "0.5.0"
}

provider "helm" {
  kubernetes { config_path = "~/.kube/config" }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}
