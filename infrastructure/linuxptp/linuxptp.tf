# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

locals {
  _yaml   = yamldecode(file(var.services_file[0]))
  _global = local._yaml.global.linuxptp

  nodes = {
    for name, svc in local._yaml.services :
    name => {
      image_tag      = try(svc.linuxptp.image_tag, local._global.image_tag)
      interface_name = svc.linuxptp.interface_name
      config         = merge(local._global.config, try(svc.linuxptp.config, {}))
    }
    if try(svc.linuxptp.enabled, false)
  }
}

resource "helm_release" "linuxptp" {
  for_each = local.nodes

  name             = "linuxptp-${each.key}"
  namespace        = "infra"
  create_namespace = false
  repository       = "https://srsran.github.io/srsRAN_Project_helm"
  chart            = "linuxptp"
  version          = var.helm_version

  values = [templatefile("${path.module}/manifests/linuxptp-values.yaml.tftpl", {
    node      = each.value
    node_name = each.key
  })]

  lifecycle { ignore_changes = [description] }
}
