resource "gitlab_tag_protection" "protected_tags" {
  for_each = var.protected_tags

  project             = var.ci_project_id
  tag                 = each.key
  create_access_level = each.value.create_access_level
}
