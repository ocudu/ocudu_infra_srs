# =============================================================================
# GitLab Project Configuration
# =============================================================================
# This file contains the configuration values for your GitLab project.
# Modify these values according to your project requirements.

# =============================================================================
# Basic Project Settings
# =============================================================================
default_branch   = "main"
visibility_level = "private" # private, internal, public

# =============================================================================
# Merge Request Configuration
# =============================================================================
merge_method                                     = "ff" # merge, rebase_merge, ff
only_allow_merge_if_pipeline_succeeds            = true
only_allow_merge_if_all_discussions_are_resolved = false
remove_source_branch_after_merge                 = true
resolve_outdated_diff_discussions                = false
squash_option                                    = "default_off" # never, always, default_on, default_off
allow_merge_on_skipped_pipeline                  = false

# =============================================================================
# CI/CD Configuration
# =============================================================================
auto_cancel_pending_pipelines = "enabled" # enabled, disabled
auto_devops_enabled           = false
build_git_strategy            = "fetch" # clone, fetch
build_timeout                 = 3600
ci_forward_deployment_enabled = false
ci_default_git_depth          = 1
ci_separated_caches           = false
keep_latest_artifact          = true
merge_pipelines_enabled       = true
merge_trains_enabled          = true

# =============================================================================
# Repository Settings
# =============================================================================
autoclose_referenced_issues = true
lfs_enabled                 = false

# =============================================================================
# Feature Access Levels
# =============================================================================
builds_access_level                  = "enabled"
container_registry_access_level      = "private"
forking_access_level                 = "enabled"
merge_requests_access_level          = "enabled"
packages_enabled                     = true
pages_access_level                   = "public"
repository_access_level              = "enabled"
requirements_access_level            = "enabled"
security_and_compliance_access_level = "private"
snippets_access_level                = "enabled"
wiki_access_level                    = "enabled"
request_access_enabled               = true

# =============================================================================
# Container Registry Configuration
# =============================================================================
container_expiration_policy = {
  cadence           = "1d"
  enabled           = true
  keep_n            = 25
  older_than        = "7d"
  name_regex_delete = ".*"
  name_regex_keep   = null
}

# =============================================================================
# Push Rules Configuration
# =============================================================================
push_rules = {
  prevent_secrets         = true
  commit_message_regex    = ".*"
  reject_unsigned_commits = false
  deny_delete_tag         = true
}

# =============================================================================
# Merge Request Approvals Configuration
# =============================================================================
mr_approvals = {
  disable_overriding_approvers_per_merge_request = true
  merge_requests_author_approval                 = true
  merge_requests_disable_committers_approval     = true
  require_password_to_approve                    = false
  reset_approvals_on_push                        = false
  selective_code_owner_removals                  = false
}

approval_rules = {
  all_members = {
    approvals_required                = 1
    rule_type                         = "any_approver"
    applies_to_all_protected_branches = true
  }
}

# =============================================================================
# Protected Branches Configuration
# =============================================================================
protected_branches = {
  main = {
    allow_force_push             = false
    code_owner_approval_required = false
    merge_access_level           = "developer"
    push_access_level            = "no one"
  }
}

# =============================================================================
# Protected Tags Configuration
# =============================================================================
protected_tags = {
  "*" = {
    create_access_level = "maintainer"
  }
}

# =============================================================================
# Pipeline Schedules Configuration
# =============================================================================
schedules = {
  watchdog = {
    description = "Watchdog"
    cron        = "00 10-18/2 * * 1-5"
    timezone    = "Europe/Madrid"
    ref         = "refs/heads/main"
    active      = true
    variables   = {}
  }
  nightly = {
    description = "Emulated Nightly"
    cron        = "00 21 * * 0-5"
    timezone    = "Europe/Madrid"
    ref         = "refs/heads/main"
    active      = true
    variables   = {}
  }
  rf_nightly = {
    description = "RF Nightly"
    cron        = "00 22 * * 0-5"
    timezone    = "Europe/Madrid"
    ref         = "refs/heads/main"
    active      = true
    variables   = {}
  }
  weekly = {
    description = "Emulated Weekly"
    cron        = "00 10 * * 6"
    timezone    = "Europe/Madrid"
    ref         = "refs/heads/main"
    active      = true
    variables   = {}
  }
}
