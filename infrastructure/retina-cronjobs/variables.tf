# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

variable "namespace" {
  description = "Kubernetes namespace to deploy cronjobs into."
  type        = string
  default     = "retina"
}

variable "suffix" {
  description = "Suffix used to name resources (ServiceAccount, ClusterRole, secrets, ConfigMaps)."
  type        = string
  default     = "cluster"
}

variable "retina_registry_uri" {
  description = "Base URI of the Retina image registry (e.g. registry.gitlab.com/ocudu/ocudu_infra_srs/retina)."
  type        = string
}

variable "retina_version" {
  description = "Launcher image tag to use for cronjob containers."
  type        = string
}

variable "gitlab_runner_token" {
  description = "GitLab runner token injected into the gitlabtoken secret consumed by the cronjobs."
  type        = string
  sensitive   = true
}

variable "runners_file" {
  type        = list(string)
  description = "Paths to <cluster>_runners.yaml files used to populate the retina-runners ConfigMap. Paths are relative to the consumer's Terraform working directory."
  default     = []

  validation {
    condition     = length(var.runners_file) > 0 && alltrue([for f in var.runners_file : fileexists(pathexpand(f))])
    error_message = "runners_file must be a non-empty list and all files must exist."
  }
}

variable "cronjobs" {
  description = "Cronjob instances to deploy. Map key is the instance name (becomes the CronJob name prefix, e.g. \"runner-manager\" → \"runner-manager-<suffix>\"). type must be one of: amarisoft-license, runner-manager."
  type = map(object({
    type       = string
    schedule   = optional(string)
    timezone   = optional(string, "Europe/Madrid")
    extra_args = optional(list(string), [])
    tolerations = optional(list(object({
      key      = optional(string)
      operator = string
      value    = optional(string)
      effect   = optional(string)
    })), [])
  }))
  default = {
    "amarisoft-license" = { type = "amarisoft-license" }
    "runner-manager"    = { type = "runner-manager" }
  }

  validation {
    condition     = alltrue([for k, v in var.cronjobs : contains(["amarisoft-license", "runner-manager"], v.type)])
    error_message = "Valid cronjob types are: amarisoft-license, runner-manager."
  }
}
