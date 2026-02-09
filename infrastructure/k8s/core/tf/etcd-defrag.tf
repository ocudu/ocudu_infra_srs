#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

resource "kubernetes_manifest" "etcd_defrag_lab" {
  manifest = yamldecode(
    file("../etcd-defrag/etcd-defrag-cronjob-lab.yaml")
  )
  
  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

}

resource "kubernetes_manifest" "etcd_defrag_datacenter" {
  manifest = yamldecode(
    file("../etcd-defrag/etcd-defrag-cronjob-datacenter.yaml")
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

}


