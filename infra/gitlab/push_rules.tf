resource "gitlab_project_push_rules" "this" {
  project                 = var.ci_project_id
  prevent_secrets         = var.push_rules.prevent_secrets
  commit_message_regex    = var.push_rules.commit_message_regex
  reject_unsigned_commits = var.push_rules.reject_unsigned_commits
  deny_delete_tag         = var.push_rules.deny_delete_tag
}
