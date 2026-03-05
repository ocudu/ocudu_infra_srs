#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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

variable "runner_update_token" {
  description = "GitLab API token used by pre/post apply null_resource provisioners to pause and unpause runners during Helm chart updates."
  type        = string
  sensitive   = true
}
