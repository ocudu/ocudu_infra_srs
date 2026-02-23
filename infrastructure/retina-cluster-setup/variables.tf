#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

# Kubernetes namespace
variable "namespace" {
  description = "Kubernetes namespace to create for Retina"
  type        = string
  default     = "retina"
}

# Registry credentials
variable "registry_auth" {
  description = "Base64-encoded docker registry auth token (base64 of 'username:token')"
  type        = string
  sensitive   = true
}

variable "registry_server" {
  description = "Docker registry server hostname"
  type        = string
  default     = "registry.gitlab.com"
}

variable "registry_secret_namespaces" {
  description = "Namespaces to deploy the docker-registry secret to"
  type        = list(string)
  default     = ["retina"]
}

# PriorityClasses to create. retina-e2e-priority is the only default but the full
# map can be overridden. At least retina-e2e-priority is required for Retina to function.
variable "priority_classes" {
  description = "PriorityClasses to create. retina-e2e-priority (value 1000000) is the only default."
  type = map(object({
    value          = number
    description    = string
    global_default = optional(bool, false)
  }))
  default = {
    retina-e2e-priority = {
      value       = 1000000
      description = "This priority class should be used for retina service pods only!"
    }
  }
}

# RBAC
variable "enable_rbac" {
  description = "Create ClusterRole, ClusterRoleBinding, Role, and RoleBinding for Retina"
  type        = bool
  default     = true
}
