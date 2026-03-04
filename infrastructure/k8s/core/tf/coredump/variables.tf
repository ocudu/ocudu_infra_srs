# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

variable "namespace" {
  type        = string
  description = "Kubernetes namespace for the coredump-cleanup DaemonSet"
  default     = "infra"
}
