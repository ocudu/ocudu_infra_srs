# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

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
