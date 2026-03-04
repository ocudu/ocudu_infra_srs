# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

# ServiceAccount
resource "kubernetes_manifest" "serviceaccount" {
  manifest = yamldecode(
    templatefile("${path.module}/../manifests/rbac/serviceaccount.yaml", {
      organization_name = var.organization_name
      namespace         = var.namespace
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}

# ClusterRole
resource "kubernetes_manifest" "clusterrole" {
  manifest = yamldecode(
    templatefile("${path.module}/../manifests/rbac/clusterrole.yaml", {
      organization_name = var.organization_name
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}

# ClusterRoleBinding
resource "kubernetes_manifest" "clusterrolebinding" {
  manifest = yamldecode(
    templatefile("${path.module}/../manifests/rbac/clusterrolebinding.yaml", {
      organization_name = var.organization_name
      namespace         = var.namespace
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

  depends_on = [
    kubernetes_manifest.serviceaccount,
    kubernetes_manifest.clusterrole
  ]
}
