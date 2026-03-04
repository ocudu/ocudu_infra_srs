# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

resource "kubernetes_manifest" "etcd_defrag" {
  manifest = yamldecode(
    templatefile("../../etcd-defrag/etcd-defrag-cronjob.yaml", {
      namespace        = var.namespace
      master_nodes     = var.master_nodes
      etcd_endpoints   = var.etcd_endpoints
      ca_cert_path     = var.ca_cert_path
      client_cert_path = var.client_cert_path
      client_key_path  = var.client_key_path
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

}
