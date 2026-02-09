#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

locals {
  # Load and merge runners from multiple files
  runners_by_file = [
    for file_path in var.runners_file : try(yamldecode(file(pathexpand(file_path))).runners, {})
  ]

  # Merge all runners by node name across all files
  runners_by_node = merge([
    for runners_map in local.runners_by_file : {
      for node_name, runner_list in runners_map :
      node_name => runner_list
    }
  ]...)

  # Filter runners based on organization_name and cluster_types field:
  # - If runner has cluster_types defined: include only if current organization_name is in the list
  # - If runner has no cluster_types: include runner (backward compatibility)
  #
  # This allows:
  # 1. Multiple organizations to share the same cluster definition file
  # 2. Each organization to deploy only their own runners
  # 3. ANY organization name to be used (not hardcoded - user-defined)
  #
  # Examples:
  #   Runner with cluster_types: ["prod", "staging"] → included if organization_name is "prod" or "staging"
  #   Runner with cluster_types: ["my-cluster"] → included if organization_name is "my-cluster"
  #   Runner with no cluster_types → included for ANY organization_name
  runners_by_node_filtered = {
    for node_name, runner_list in local.runners_by_node :
    node_name => [
      for r in runner_list : r
      if(
        length(try(r.cluster_types, [])) == 0 || contains(r.cluster_types, var.organization_name)
      )
    ]
  }

  runners_b64 = base64encode(jsonencode(local.runners_by_node_filtered))
}

# Dedicated ConfigMap for runner-manager inputs (owned by Terraform).
resource "kubernetes_manifest" "retina_runners_configmap" {
  manifest = {
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {
      name      = "retina-runners-${var.organization_name}"
      namespace = "retina"
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
