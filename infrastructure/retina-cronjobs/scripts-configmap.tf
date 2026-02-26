#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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
