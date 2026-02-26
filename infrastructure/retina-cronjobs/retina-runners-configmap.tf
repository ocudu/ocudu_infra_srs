# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

locals {
  runners_by_file = [
    for file_path in var.runners_file : try(yamldecode(file(pathexpand(file_path))).runners, {})
  ]

  runners_by_node = merge([
    for runners_map in local.runners_by_file : {
      for node_name, runner_list in runners_map :
      node_name => runner_list
    }
  ]...)

  runners_by_node_filtered = {
    for node_name, runner_list in local.runners_by_node :
    node_name => [
      for r in runner_list : r
      if(
        length(try(r.cluster_types, [])) == 0 || contains(r.cluster_types, var.suffix)
      )
    ]
  }

  runners_b64 = base64encode(jsonencode(local.runners_by_node_filtered))
}

resource "kubernetes_manifest" "retina_runners_configmap" {
  manifest = {
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {
      name      = "retina-runners-${var.suffix}"
      namespace = var.namespace
    }
    data = {
      runners = local.runners_b64
    }
  }

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}
