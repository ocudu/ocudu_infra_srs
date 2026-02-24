#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

data "external" "cluster_info" {
  program = ["retina-deploy-cluster", "--input", var.cluster_config_path, "--dry-run"]
}

resource "kubernetes_config_map_v1" "retina_info" {
  metadata {
    name      = "retina-info"
    namespace = var.namespace
  }

  data = data.external.cluster_info.result
}
