# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

variable "cluster_config_path" {
  description = "Path to the cluster YAML file (absolute, or relative to the consumer root directory)."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace where the retina-info ConfigMap is created."
  type        = string
  default     = "retina"
}
