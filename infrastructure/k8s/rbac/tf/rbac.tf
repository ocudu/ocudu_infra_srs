#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

locals {
  # RBAC manifests are copied to infrastructure/rbac/ in the CI workspace
  # From TF_DIR (infrastructure/k8s/rbac/tf), go up 3 levels and into rbac/
  rbac_manifest_dir = "${path.module}/../../../rbac"
  rbac_manifests    = fileset(local.rbac_manifest_dir, "*.yaml")
}

resource "kubernetes_manifest" "rbac" {
  for_each = local.rbac_manifests

  manifest = yamldecode(file("${local.rbac_manifest_dir}/${each.value}"))

  # Force conflicts to handle resources created with kubectl
  field_manager {
    force_conflicts = true
  }

  # Workaround for known Kubernetes provider bug with PriorityClass globalDefault
  # This field can be null or false, both are valid and equivalent
  computed_fields = contains(["prio-gitlab.yaml", "prio-nightly.yaml", "prio-retina.yaml"], each.value) ? ["object.globalDefault"] : []
}
