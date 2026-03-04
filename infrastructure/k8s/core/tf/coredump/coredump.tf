# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

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
