#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

variable "cluster_config_path" {
  description = "Path to the cluster YAML file (absolute, or relative to the consumer root directory)."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace where the retina-info ConfigMap is created."
  type        = string
  default     = "retina"
}
