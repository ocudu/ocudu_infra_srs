#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

output "namespace" {
  description = "Kubernetes namespace created for Retina"
  value       = kubernetes_namespace_v1.retina.metadata[0].name
}

output "registry_secret_name" {
  description = "Name of the docker-registry secret"
  value       = "registry-credentials"
}

output "registry_secret_namespaces" {
  description = "Namespaces where the registry secret was deployed"
  value       = var.registry_secret_namespaces
}
