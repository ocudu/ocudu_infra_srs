# Infrastructure as Code Overview

This document describes how the IaC solution is structured and how to use it to configure a new cluster.

## Architecture

The solution is split across two repositories:

- **`infra_srs` (this repo, public)** — provides reusable Terraform modules and the shared CI template.
- **Consumer repo (your private repo)** — holds cluster-specific config files and `main.tf` consumers that call the modules.

```text
infra_srs/infrastructure/
├── .gitlab-ci.yml          # Shared CI template (fmt/validate/plan/apply)
├── tuned/                  # Terraform module — TuneD kernel tuning
├── linuxptp/               # Terraform module — LinuxPTP time sync
├── gitlab-runner/          # Terraform module — GitLab Runners
├── retina-cluster-setup/   # Terraform module — Retina namespace and RBAC
├── retina-cluster-definition/  # Terraform module — Retina cluster ConfigMap
└── retina-cronjobs/        # Terraform module — Retina CronJobs

your-private-infra-repo/
├── .gitlab-ci.yml                      # Trigger jobs that call the shared CI template
└── cluster_definition/
    ├── retina_info.yaml                # Retina Cluster Definition
    └── runners.yaml                    # GitLab runner config
    ├── services.yaml                   # tuned + linuxptp config
    ├── main.tf                         # Consumer tf. Can use one for all (one tf state) or multiples (recommended)
```

## Available modules

| Module | Description | Config source | README |
| --- | --- | --- | --- |
| `tuned` | TuneD kernel tuning profiles and startup scripts, one Helm release per node | `services.yaml` | [tuned/README.md](../tuned/README.md) |
| `linuxptp` | LinuxPTP PTP time sync daemon, one Helm release per node | `services.yaml` | [linuxptp/README.md](../linuxptp/README.md) |
| `gitlab-runner` | GitLab Runners via the official Helm chart, with quarantine logic | `runners.yaml` | [gitlab-runner/README.md](../gitlab-runner/README.md) |
| `retina-cluster-setup` | Retina namespace, RBAC, and registry credentials | `retina_info.yml` | [retina-cluster-setup/README.md](../retina-cluster-setup/README.md) |
| `retina-cluster-definition` | `retina-info` ConfigMap with cluster topology | `retina_info.yml` | [retina-cluster-definition/README.md](../retina-cluster-definition/README.md) |
| `retina-cronjobs` | Amarisoft license sync and runner-manager CronJobs | `runners.yaml` | [retina-cronjobs/README.md](../retina-cronjobs/README.md) |

## Consumer repo structure

Each module deployment can be a separate Terraform root module (its own `main.tf`). This gives independent state, targeted applies, and clear separation of concerns. Another option is to put different modules in the same root module once they're related (f.e. `retina/main.tf` for all retina modules, `runners/main.tf` and `services/main.tf`).

To see a full example of a cluster using all modules provided in this repo, go to the [example folder](../example/README.md).

### `retina_info.yaml`

See the [Retina Cluster Setup docs](../../retina/_docs/02_cluster_setup.md#node-definitions).

### `services.yaml`

A single file per cluster that configures `tuned` and `linuxptp`. It has two top-level sections:

- **`global`**: Default image, chart, and config values shared by all nodes.
- **`services`**: Per-node overrides, keyed by Kubernetes node name.

```yaml
global:
  tuned:
    image:
      repository: registry.gitlab.com/ocudu/ocudu_elements/ocudu_helm/tuned-agent
      tag: "v2.21.0_1.0.0"
      pullPolicy: IfNotPresent
    hostPathTuned: /usr/lib/tuned
    securityContext:
      privileged: true
    restartOnConfigChange: true
    reboot:
      enabled: true
      cmd: /sbin/shutdown -r +1 'tuned profile applied by helm'
      markerDir: /var/lib/tuned-helm
  linuxptp:
    image_tag: "v4.4_2.0.0"
    config:
      dataset_comparison: G.8275.x
      domainNumber: 24
      network_transport: L2
      delay_mechanism: E2E
      time_stamping: hardware
      # ... full ptp4l config

services:
  my-node:
    tuned:
      enabled: true
      profileContent: |-
        [main]
        summary=My profile
        ...
      startupScriptContent: |-
        #!/bin/bash
        ...
    linuxptp:
      enabled: true
      interface_name: ename
      config:                         # merged on top of global config
        summary_interval: -3
```

See [tuned/README.md](../tuned/README.md) and [linuxptp/README.md](../linuxptp/README.md) for the full field reference.

### `runners.yaml`

Configures GitLab Runners deployed on the cluster. Runners are grouped by the Kubernetes node they run on.

```yaml
global:
  image:
    registry: registry.gitlab.com
    image: gitlab-org/gitlab-runner
    tag: ubuntu-v18.2.0
  gitlab_url: https://gitlab.com/
  cache:
    type: s3
    path: gl-runner-cache
    s3:
      server_address: "10.0.0.1:9000"
      bucket_name: "my-bucket"
      insecure: true

runners:
  my-node:
    - id: 12345678
      name: glr-my-runner
      cluster_types: [my-cluster-type]
      token: glrt-xxxx
      concurrent: 4
      tags: amd64, build
      cpu_request: 4
      cpu_limit: 4
      memory_request: 8Gi
      memory_limit: 8Gi
      node_tolerations:
        machine=my-node: NoSchedule
```

See [gitlab-runner/README.md](../gitlab-runner/README.md) for the full field reference.

## CI integration

Each module deployment is triggered by a job in the consumer repo's `.gitlab-ci.yml`. Jobs use the shared `infrastructure/.gitlab-ci.yml` component via `inputs:`:

```yaml
terraform for tuned:
  stage: child
  rules:
    - if: $ON_MR
      changes:
        paths:
          - cluster_definition/my-cluster/services.yaml
    - if: $ON_DEFAULT_BRANCH
      changes:
        paths:
          - cluster_definition/my-cluster/services.yaml
        compare_to: "$CI_COMMIT_BEFORE_SHA"
    - if: $CI_PIPELINE_SCHEDULE_DESCRIPTION =~ /^Infra Update/
  trigger:
    include:
      - project: &infra_srs_path ocudu/ocudu_infra_srs
        ref: &infra_srs_ref main
        file: infrastructure/.gitlab-ci.yml
        inputs:
          infra_srs_path: *infra_srs_path
          infra_srs_ref: *infra_srs_ref
          kubeconfig_var: MY_KUBECONFIG         # file-type CI/CD variable
          runner_tags: [my-runner-tag]
          state_name: tuned                     # unique per cluster
          root_dir: cluster_definition/my-cluster/tuned
    strategy: mirror
  needs: []
```

For the full CI template reference and available inputs, see [opentofu.md](./04_opentofu.md).

## Adding a new cluster

See an [example of a complete cluster](../example/README.md).

1. **Create config files** in your consumer repo.

2. **Create consumer `main.tf` files** — Create one per module to deploy or combine multiple modules into one. See each module's README for the exact consumer template. Use `abspath("${path.module}/....yaml")` to pass the config path.

3. **Add import blocks** to the consumer `main.tf` if Helm releases already exist in the cluster.

4. **Add CI trigger jobs** to `.gitlab-ci.yml`, following the pattern above.

5. **Set CI/CD variables** in your GitLab project:

 | in .gitlab-ci.yml | variable name (example) | variable type | Description |
 |-------|-------------------------|---------------|-------------|
 | `kubeconfig_var` | `KUBECONFIG` | file | kubeconfig content |
 | `TF_VAR_registry_auth` | `REGISTRY_AUTH` | var | Base64-encoded `username:token` to access the Retina registry |
 | `TF_VAR_gitlab_runner_token` | `RUNNER_TOKEN` | var | GitLab API token used to pause/unpause runners during updates |
 | `RETINA_REGISTRY_URI` | | | Retina Registry URL (f.e. `registry.gitlab.com/ocudu/ocudu_infra_srs/retina`) |
 | `RETINA_PYPI_INDEX` | | | Retina pypi index URL (f.e. `https://gitlab.com/api/v4/projects/78028160/packages/pypi/simple`) |

1. **Manually install a Terraform runner on the cluster** — This runner must exist before any IaC job can run, so it cannot be managed by the `gitlab-runner` module itself (doing so would destroy it while trying to recreate it). [Install it manually](https://docs.gitlab.com/runner/install):

   The runner needs:
   - A tag matching what you will pass as `runner_tags` in your CI trigger jobs (e.g. `terraform-my-cluster`)
   - A kube config or in-cluster service account with permissions to read/write the namespaces the modules deploy into (`infra`, `gitlab-runner`, `retina`, etc.)
   - Network access to the GitLab instance (for Terraform state backend)

   Once this runner is in place, all subsequent infrastructure changes (including other runners) can be managed through IaC.
