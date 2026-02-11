#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

resource "kubernetes_manifest" "coredump_cleanup" {
  manifest = yamldecode(
    templatefile("../../coredump/coredump-cleanup.yml", {
      namespace = var.namespace
    })
  )
  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

}
