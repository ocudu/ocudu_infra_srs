# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

resource "kubernetes_manifest" "scripts_configmap" {
  manifest = {
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {
      name      = "retina-scripts-${var.suffix}"
      namespace = var.namespace
    }
    data = {
      "amarisoft_license.py" = file("${path.module}/scripts/amarisoft_license.py")
      "retina_runner.py"     = file("${path.module}/scripts/retina_runner.py")
    }
  }

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}
