# Retina Cronjobs

Terraform module that deploys the Retina CronJobs and their supporting resources onto a cluster already provisioned by `retina-cluster-setup`.

## What it deploys

| Resource | Description |
| --- | --- |
| `ServiceAccount` | `retina-cronjobs-sa-<suffix>` — identity for cronjob pods |
| `ClusterRoleBinding` | Binds the SA to `retina-cluster-role` (created by `retina-cluster-setup`) |
| `RoleBinding` | Binds the SA to `retina-role` in `var.namespace` (created by `retina-cluster-setup`) |
| `Secret` | `gitlabtoken-<suffix>` — GitLab runner token consumed by the cronjobs |
| `ConfigMap` | `retina-runners-<suffix>` — runner definitions for the runner-manager cronjob |
| `ConfigMap` | `retina-scripts-<suffix>` — Python entry-point scripts mounted into cronjob pods |
| `CronJob` | `amarisoft-license-<suffix>` and/or `runner-manager-<suffix>` |

All resources are deployed into `var.namespace` (default: `retina`), which must already exist (created by `retina-cluster-setup`). The RBAC roles themselves are **not** created here — this module only creates bindings to the roles owned by `retina-cluster-setup`.

## CronJobs

- `amarisoft-license` type:
  - Default schedule: `* * * * *` (every minute)
  - Syncs Amarisoft license usage with Retina reservations. It checks the licenses status in Amarisoft License Server and reserve / unreserve the equivalent resource in retina (if exists). This avoids conflicts when an Amarisoft License is being used outside Retina.
- `runner-manager` type:
  - Default schedule: `*/1 7-19 * * 1-5` (07:00–19:59 Mon–Fri)
  - Manages GitLab runner pod lifecycle

Both cronjobs use `${var.retina_registry_uri}/launcher:${var.retina_version}` as the base image. The entry-point scripts (`amarisoft_license.py`, `retina_runner.py`) live in `scripts/` and are deployed as a ConfigMap mounted at `/usr/local/bin/` — no custom image build required.

Per-cronjob schedule and tolerations are configured via the `cronjobs` input variable.

## Prerequisites

`retina-cluster-setup` must be applied first. This module depends on:

- The `retina` namespace existing.
- The `retina-cluster-role` ClusterRole and `retina-role` Role being present.

## Inputs

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `suffix` | `string` | `"cluster"` | Suffix appended to all resource names |
| `namespace` | `string` | `"retina"` | Namespace to deploy into (must already exist) |
| `retina_registry_uri` | `string` | required | Base image registry URI (e.g. `registry.gitlab.com/ocudu/ocudu_infra_srs/retina`) |
| `retina_version` | `string` | required | Launcher image tag |
| `gitlab_runner_token` | `string` | required, sensitive | GitLab runner token (pass as `TF_VAR_gitlab_runner_token`) |
| `runners_file` | `list(string)` | required | Paths to runner YAML files (relative to Terraform working directory) |
| `cronjobs` | `map(object)` | both cronjobs with defaults | Which cronjobs to deploy and their per-cronjob config (see below) |

### `cronjobs` input

Map key is the cronjob name (`amarisoft-license` or `runner-manager`). Each entry is optional and can override the default schedule and set pod tolerations for that specific cronjob.

```hcl
cronjobs = {
  "runner-manager" = {
    schedule = "*/5 8-18 * * 1-5"  # optional — omit to keep the module default
    tolerations = [                 # optional — omit for no tolerations
      {
        key      = "node-role.kubernetes.io/infra"  # optional for Exists operator
        operator = "Equal"                          # "Equal" or "Exists"
        value    = "true"                           # optional when operator = "Exists"
        effect   = "NoSchedule"                     # optional
      }
    ]
  }
  "amarisoft-license" = {}  # use module defaults for schedule and tolerations
}
```

Omitting a cronjob key disables it entirely. To deploy both with defaults:

```hcl
cronjobs = {
  "runner-manager"    = {}
  "amarisoft-license" = {}
}
```

## Using this module

Consumer `main.tf` example:

```hcl
module "retina_cronjobs" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/retina-cronjobs?ref=${var.infra_srs_ref}"

  suffix              = "my-cluster"
  namespace           = "retina"
  retina_registry_uri = var.retina_registry_uri
  retina_version      = var.retina_version
  gitlab_runner_token = var.gitlab_runner_token
  runners_file        = [abspath("${path.root}/../../my_cluster_runners.yaml")]
  cronjobs = {
    "runner-manager"    = {}
    "amarisoft-license" = {}
  }
}
```

For CI template details see [opentofu.md](../_docs/04_opentofu.md).

- `TF_VAR_gitlab_runner_token` must be configured as a masked CI/CD variable in GitLab project settings.
- `RETINA_VERSION` and `RETINA_REGISTRY_URI` are injected automatically by the shared CI template.
