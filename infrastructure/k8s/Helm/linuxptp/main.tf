#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

terraform {
  backend "http" {}

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "2.13.2"
    }
  }
}

variable "linuxptp_version" {
  type    = string
  default = "1.3.0"
}

provider "helm" {
  kubernetes { config_path = "~/.kube/config" }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}
