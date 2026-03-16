# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

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
