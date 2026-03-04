# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

locals {
  image_tag = var.retina_cronjobs_version

  cronjobs = {
    "amarisoft-license" = {
      template = "${path.module}/../manifests/cronjobs/amarisoft-license.yaml"
    }
    "runner-manager" = {
      template = "${path.module}/../manifests/cronjobs/runner-manager.yaml"
    }
    "cluster-cleanup" = {
      template = "${path.module}/../manifests/cronjobs/cluster-cleanup.yaml"
    }
    "infrastructure-issues-notifier" = {
      template = "${path.module}/../manifests/cronjobs/infrastructure-issues-notifier.yaml"
    }
  }
}

resource "kubernetes_manifest" "cronjobs" {
  for_each = {
    for key, cfg in local.cronjobs : key => cfg
    if contains(var.enabled_cronjobs, key)
  }

  manifest = yamldecode(
    templatefile(each.value.template, {
      organization_name = var.organization_name
      namespace         = var.namespace
      image_repository  = var.image_repository
      image_tag         = local.image_tag
      taint_key         = var.taint_key
      taint_value       = var.taint_value
      gitlab_group_id   = var.gitlab_group_id
    })
  )

  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }

  depends_on = [
    kubernetes_manifest.serviceaccount,
    kubernetes_manifest.retina_runners_configmap,
    kubernetes_secret_v1.gitlab_runner_token
  ]
}
