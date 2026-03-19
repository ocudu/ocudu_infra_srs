# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

locals {
  _yaml   = yamldecode(file(var.services_file[0]))
  _global = local._yaml.global.tuned

  nodes = {
    for name, svc in local._yaml.services :
    name => {
      image_repository         = try(svc.tuned.image.repository, local._global.image.repository)
      image_tag                = try(svc.tuned.image.tag, local._global.image.tag)
      image_pull_policy        = try(svc.tuned.image.pullPolicy, local._global.image.pullPolicy)
      profile_name             = try(svc.tuned.profile_name, "ocudu-tuned-${name}")
      profile_content          = svc.tuned.profileContent
      startup_script_content   = try(svc.tuned.startupScriptContent, "")
      host_path_tuned          = try(svc.tuned.hostPathTuned, local._global.hostPathTuned)
      node_selector            = try(svc.tuned.nodeSelector, local._global.nodeSelector)
      security_context         = try(svc.tuned.securityContext, local._global.securityContext)
      resources                = try(svc.tuned.resources, local._global.resources)
      annotations              = try(svc.tuned.annotations, local._global.annotations)
      restart_on_config_change = try(svc.tuned.restartOnConfigChange, local._global.restartOnConfigChange)
      reboot                   = try(svc.tuned.reboot, local._global.reboot)
      tolerations = [
        for t in try(svc.tuned.tolerations, [{ key = "machine", operator = "Equal", value = name, effect = "NoSchedule" }]) : {
          key      = t.key
          operator = t.operator
          value    = try(t.value, null)
          effect   = t.effect
        }
      ]
    }
    if try(svc.tuned.enabled, false)
  }
}

resource "helm_release" "tuned" {
  for_each = local.nodes

  name             = "tuned-${each.key}"
  namespace        = "infra"
  create_namespace = false
  repository       = "oci://registry.gitlab.com/ocudu/ocudu_elements/ocudu_helm"
  chart            = "tuned"
  version          = var.helm_version

  values = [templatefile("${path.module}/manifests/tuned-values.yaml.tftpl", {
    node      = each.value
    node_name = each.key
  })]

  lifecycle { ignore_changes = [description] }
}
