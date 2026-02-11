#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

variable "namespace" {
  type        = string
  description = "Kubernetes namespace for the etcd-defrag cronjob"
  default     = "infra"
}

variable "master_nodes" {
  type        = list(string)
  description = "List of master node hostnames for nodeAffinity scheduling"
}

variable "etcd_endpoints" {
  type        = string
  description = "Comma-separated etcd endpoints (e.g., https://10.0.0.1:2379,https://10.0.0.2:2379)"
}

variable "ca_cert_path" {
  type        = string
  description = "Host path to the etcd CA certificate"
}

variable "client_cert_path" {
  type        = string
  description = "Host path to the etcd client certificate"
}

variable "client_key_path" {
  type        = string
  description = "Host path to the etcd client key"
}
