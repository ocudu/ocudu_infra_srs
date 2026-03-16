# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

variable "services_file" {
  description = "Path to the cluster services.yaml file."
  type        = list(string)
  validation {
    condition     = length(var.services_file) > 0 && alltrue([for f in var.services_file : fileexists(f)])
    error_message = "services_file must be non-empty and all files must exist."
  }
}

variable "helm_version" {
  description = "Tuned Helm chart version."
  type        = string
  default     = "0.5.0"
}
