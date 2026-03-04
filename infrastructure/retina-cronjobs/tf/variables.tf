# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

variable "kubeconfig" {
  type    = string
  default = "~/.kube/config"
}
variable "namespace" { type = string }
variable "retina_cronjobs_version" { type = string }
variable "taint_key" { type = string }
variable "taint_value" { type = string }
variable "gitlab_group_id" { type = string }
#
# Retina runner Terraform variables
#

variable "organization_name" { type = string }

variable "runners_file" {
  type        = list(string)
  description = "List of paths to <cluster>_runners.yaml files used to populate the dedicated runners ConfigMap (namespace: retina). Supports multiple files to allow cross-cluster organization deployments. Paths are relative to the parent repo (e.g., infrastructure repo)."
  default     = []

  validation {
    condition     = length(var.runners_file) > 0 && alltrue([for f in var.runners_file : fileexists(pathexpand(f))])
    error_message = "runners_file must be a non-empty list and all files must exist. Files should be in your private repo, e.g., [\"cluster_definition/lab_cluster_runners.yaml\"]"
  }
}

variable "enabled_cronjobs" {
  type        = list(string)
  description = "List of cronjob keys to enable. Valid values: cluster-cleanup, runner-manager, amarisoft-license, infrastructure-issues-notifier"
  default     = []
}

variable "image_repository" {
  type    = string
  default = "registry.gitlab.com/ocudu/ocudu_infra_srs/retina/cronjobs"
}
