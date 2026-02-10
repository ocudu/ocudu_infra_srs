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

variable "kubeconfig" { type = string }
variable "authToken" { type = string }
variable "namespaces" {
  type        = list(string)
  description = "List of namespaces to deploy registry credentials to"
}

provider "helm" {
  kubernetes { config_path = var.kubeconfig }
}

provider "kubernetes" {
  config_path = var.kubeconfig
}

# Deploy registry credentials to each namespace
resource "helm_release" "registry-credentials" {
  for_each = toset(var.namespaces)

  name      = "registry-credentials"
  namespace = each.value
  chart     = "../registry-credentials/"
  version   = "0.1.2"

  values = [
    file("../registry-credentials/values.yaml"),
  ]

  set_list {
    name  = "namespaces"
    value = [each.value]
  }

  set_sensitive {
    name  = "authToken"
    value = var.authToken
  }

  lifecycle {
    ignore_changes = [
      description
    ]
  }
}
