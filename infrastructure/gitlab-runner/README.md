# GitLab Runner

Terraform module that deploys GitLab Runners onto a Kubernetes cluster using the official [gitlab-runner Helm chart](https://charts.gitlab.io).

Runner quarantine is handled inside Terraform: each runner is paused (and its jobs drained) before the Helm release is updated, and unpaused afterwards.

## What it deploys

| Resource | Description |
| --- | --- |
| `helm_release` | One `gitlab-runner` release per runner defined in `runners_file` matching `cluster_type` |
| `null_resource` (pre-apply) | Pauses each runner and drains running jobs before the Helm update |
| `null_resource` (post-apply) | Unpauses each runner after the Helm release is updated |

All releases are deployed into the `gitlab-runner` namespace (created automatically).

## Runner definition format

Runners are defined in a YAML file shared with the cluster directory. The file must contain
a `gitlab_runner` section (cluster-level Helm values) and a `runners` section
(per-runner pod configuration):

```yaml
gitlab_runner:
  image:
    registry: registry.gitlab.com
    image: gitlab-org/gitlab-runner
    tag: ubuntu-v18.2.0
  gitlab_url: https://gitlab.com/
  cache:
    type: s3
    path: gl-runner-amd64
    s3:
      server_address: 10.12.1.227:9000
      access_key: minio-admin
      secret_key: s0ftwareradi0
      bucket_name: my-bucket
      insecure: true
  host_aliases:              # optional — injects entries into /etc/hosts of runner pods
    ip: "10.12.1.99"
    hostnames:
      - "lb-apiserver.kubernetes.local"

runners:
  node-name:
    - id: 12345678           # GitLab runner ID
      name: glr-my-runner    # becomes the Helm release name
      cluster_types:         # optional — omit to deploy to all clusters
        - my-cluster-type
      token: glrt-xxxx       # runner authentication token
      concurrent: 4
      tags: mytag
      cpu_request: 4
      cpu_limit: 4
      memory_request: 8Gi
      memory_limit: 8Gi
      node_tolerations:
        machine=node-name: NoSchedule
```

For a full list of supported runner fields see `manifests/runner-values.yaml.tftpl`.

## Inputs

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `runners_file` | `list(string)` | required | Paths to runner YAML files |
| `cluster_type` | `string` | required | Only runners with a matching `cluster_types` entry are deployed; runners without `cluster_types` deploy to all clusters |
| `runner_update_token` | `string` | required, sensitive | GitLab API token used to pause/unpause runners during updates |
| `helm_version` | `string` | `"0.79.1"` | GitLab Runner Helm chart version |

## CUsing this module

Consumer `main.tf`:

```hcl
terraform {
  required_providers {
    helm = { source = "hashicorp/helm"; version = "~> 3.0" }
  }
  backend "http" {}
}

variable "infra_srs_path"      { type = string }
variable "infra_srs_ref"       { type = string }
variable "runner_update_token" {
  type      = string
  sensitive = true
}

provider "helm" {}

module "gitlab_runners" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/gitlab-runner?ref=${var.infra_srs_ref}"

  runners_file        = [abspath("${path.module}/...runners.yaml")]
  cluster_type        = "my-type"
  runner_update_token = var.runner_update_token
}
```

For CI template details see [infrastructure/opentofu.md](../opentofu.md). Please define `TF_VAR_runner_update_token`, which must be configured as a masked CI/CD variable in GitLab project settings.
