#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

resource "kubernetes_secret_v1" "registry_credentials" {
  for_each = toset(var.registry_secret_namespaces)

  metadata {
    name      = "registry-credentials"
    namespace = each.value
  }

  type = "kubernetes.io/dockerconfigjson"

  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        (var.registry_server) = {
          auth = var.registry_auth
        }
      }
    })
  }

  depends_on = [kubernetes_namespace_v1.retina]
}
