terraform {
  required_providers {
    gitlab = {
      source  = "gitlabhq/gitlab"
      version = ">= 18.0"
    }
  }
  backend "http" {}
}

provider "gitlab" {
  # https://search.opentofu.org/provider/opentofu/gitlab/latest
  # It uses GITLAB_TOKEN environment variable to authenticate
  # It uses GITLAB_BASE_URL environment variable to set the GitLab instance URL. If not defined, it defaults to gitlab.com
}
