#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

variable "services_file" {
  description = "Path to the cluster services.yaml file."
  type        = list(string)
  validation {
    condition     = length(var.services_file) > 0 && alltrue([for f in var.services_file : fileexists(f)])
    error_message = "services_file must be non-empty and all files must exist."
  }
}

variable "helm_version" {
  description = "Linuxptp Helm chart version."
  type        = string
  default     = "1.3.0"
}
