#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

resource "kubernetes_cluster_role_v1" "retina" {
  count = var.enable_rbac ? 1 : 0

  metadata {
    name = "retina-cluster-role"
  }

  rule {
    api_groups = [""]
    resources  = ["nodes"]
    verbs      = ["get", "list", "watch"]
  }

  rule {
    api_groups = [""]
    resources  = ["pods"]
    verbs      = ["get", "list", "watch"]
  }

  rule {
    api_groups = ["policy"]
    resources  = ["pods/eviction"]
    verbs      = ["create"]
  }

  rule {
    api_groups = ["scheduling.k8s.io"]
    resources  = ["priorityclasses"]
    verbs      = ["get", "list", "watch"]
  }
}

resource "kubernetes_cluster_role_binding_v1" "retina" {
  count = var.enable_rbac ? 1 : 0

  metadata {
    name = "retina-cluster-rolebinding"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "retina-cluster-role"
  }

  subject {
    kind      = "User"
    name      = "retina"
    api_group = "rbac.authorization.k8s.io"
  }
}

resource "kubernetes_role_v1" "retina" {
  count = var.enable_rbac ? 1 : 0

  metadata {
    name      = "retina-role"
    namespace = var.namespace
  }

  rule {
    api_groups = [""]
    resources  = ["pods", "configmaps", "services"]
    verbs      = ["create", "delete", "list"]
  }

  rule {
    api_groups = [""]
    resources  = ["pods"]
    verbs      = ["watch"]
  }

  rule {
    api_groups = ["apps"]
    resources  = ["deployments"]
    verbs      = ["create", "delete", "list"]
  }

  rule {
    api_groups = [""]
    resources  = ["pods/exec"]
    verbs      = ["create"]
  }

  rule {
    api_groups = [""]
    resources  = ["pods/log"]
    verbs      = ["get"]
  }

  depends_on = [kubernetes_namespace_v1.retina]
}

resource "kubernetes_role_binding_v1" "retina" {
  count = var.enable_rbac ? 1 : 0

  metadata {
    name      = "retina-rolebinding"
    namespace = var.namespace
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = "retina-role"
  }

  subject {
    kind      = "User"
    name      = "retina"
    api_group = "rbac.authorization.k8s.io"
  }

  depends_on = [kubernetes_namespace_v1.retina]
}
