#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

resource "kubernetes_priority_class_v1" "this" {
  for_each = var.priority_classes

  metadata {
    name = each.key
  }
  value          = each.value.value
  description    = each.value.description
  global_default = each.value.global_default
}
