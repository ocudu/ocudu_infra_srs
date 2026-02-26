# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

resource "kubernetes_manifest" "serviceaccount" {
  manifest = yamldecode(
    templatefile("${path.module}/manifests/rbac/serviceaccount.yaml", {
      suffix = var.suffix
      namespace         = var.namespace
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}

# Bind the cronjob SA to the ClusterRole already created by retina-cluster-setup.
resource "kubernetes_manifest" "clusterrolebinding" {
  manifest = yamldecode(
    templatefile("${path.module}/manifests/rbac/clusterrolebinding.yaml", {
      suffix = var.suffix
      namespace         = var.namespace
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

  depends_on = [kubernetes_manifest.serviceaccount]
}

# Bind the cronjob SA to the namespace Role already created by retina-cluster-setup.
resource "kubernetes_manifest" "rolebinding" {
  manifest = yamldecode(
    templatefile("${path.module}/manifests/rbac/rolebinding.yaml", {
      suffix = var.suffix
      namespace         = var.namespace
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

  depends_on = [kubernetes_manifest.serviceaccount]
}
