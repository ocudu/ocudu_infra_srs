# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

terraform {
  backend "http" {}
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

