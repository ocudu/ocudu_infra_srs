# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

resource "kubernetes_secret_v1" "registry_credentials" {
  for_each = toset(var.registry_secret_namespaces)

  metadata {
    name      = "registry-credentials"
    namespace = each.value
  }

  type = "kubernetes.io/dockerconfigjson"

  data = {
    ".dockerconfigjson" = base64decode(var.registry_auth)
  }

  depends_on = [kubernetes_namespace_v1.retina]
}
