# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

variable "runners_file" {
  description = "Paths to *_runners.yaml files. Same format as retina-cronjobs module."
  type        = list(string)

  validation {
    condition     = length(var.runners_file) > 0 && alltrue([for f in var.runners_file : fileexists(pathexpand(f))])
    error_message = "runners_file must be non-empty and all files must exist."
  }
}

variable "cluster_type" {
  description = "Cluster type filter (e.g. 'srs-bcn'). Only runners whose cluster_types list contains this value are deployed. Runners without a cluster_types field are deployed to all clusters."
  type        = string
}

variable "helm_version" {
  description = "GitLab Runner Helm chart version."
  type        = string
  default     = "0.79.1"
}

variable "gitlab_runner_token" {
  description = "GitLab API token used by pre/post apply null_resource provisioners to pause and unpause runners during Helm chart updates."
  type        = string
  sensitive   = true
}

variable "certs_secret_name" {
  description = "Name of a Kubernetes secret in the gitlab-runner namespace containing CA certs (e.g. gitlab.lab.mil.crt). Mounted by the runner pod to trust custom CAs during registration."
  type        = string
  default     = null
}
