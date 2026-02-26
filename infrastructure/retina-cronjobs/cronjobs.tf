#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

locals {
  cronjob_defaults = {
    "amarisoft-license" = {
      template         = "${path.module}/manifests/cronjobs/amarisoft-license.yaml"
      default_schedule = "* * * * *"
    }
    "runner-manager" = {
      template         = "${path.module}/manifests/cronjobs/runner-manager.yaml"
      default_schedule = "*/1 7-19 * * 1-5"
    }
  }
}

resource "kubernetes_manifest" "cronjobs" {
  for_each = var.cronjobs

  manifest = yamldecode(
    templatefile(local.cronjob_defaults[each.value.type].template, {
      name                = each.key
      suffix              = var.suffix
      namespace           = var.namespace
      retina_registry_uri = var.retina_registry_uri
      retina_version      = var.retina_version
      schedule            = coalesce(each.value.schedule, local.cronjob_defaults[each.value.type].default_schedule)
      timezone            = each.value.timezone
      extra_args          = each.value.extra_args
      tolerations         = each.value.tolerations
      scripts_configmap   = "retina-scripts-${var.suffix}"
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

  depends_on = [
    kubernetes_manifest.serviceaccount,
    kubernetes_manifest.retina_runners_configmap,
    kubernetes_manifest.scripts_configmap,
    kubernetes_secret_v1.gitlab_runner_token,
  ]
}
