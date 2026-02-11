#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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
