# Infrastructure Automation

This directory contains reusable CI/CD templates and configuration scripts for deploying and managing Retina test lab infrastructure.

## Overview

The infrastructure automation provides **generic, reusable CI/CD templates** for:

- **GitLab Runner deployment** - Automated deployment of GitLab runners for build, IAC, and E2E tests
- **Kubernetes core resources** - Coredump cleanup DaemonSet and etcd defragmentation CronJobs
- **RBAC configuration** - Kubernetes role-based access control setup
- **Helm services** - Tuned and LinuxPTP service deployments
- **Retina runner management** - Automated runner scheduling and cleanup cronjobs
- **Configuration generation** - Python-based Jinja2 templating for cluster-specific configs

**Key Design Principles:**

- **100% Generic**: No hardcoded cluster names, IDs, or organization-specific values
- **Public/Private Split**: Templates in public repo, secrets/configs in your private repo
- **Parameterized**: All cluster-specific values passed as CI/CD variables
- **Replicable**: Any organization can use these templates with their own infrastructure

## Architecture

```text
infrastructure/
├── base/                            # Reusable CI/CD base definitions
│   └── terraform.yml                # Terraform job template with GitLab state backend
├── images/
│   └── terraform/                   # Custom Terraform Docker image
│       ├── Dockerfile               # Terraform + Python + tools
│       └── .gitlab-ci.yml           # CI to build and publish image
├── generator/                       # Configuration generation tooling
│   ├── generate.py                  # Main generation script
│   ├── templates/                   # Jinja2 templates for Terraform and Helm
│   └── scripts/                     # Utility scripts (detect_changes.sh, etc.)
├── gitlab-runner/                   # GitLab runner deployment
│   ├── .gitlab-ci.yml               # Generic runner deployment pipeline
│   └── ...
├── k8s/
│   ├── core/                        # Core k8s resources (coredump, etcd-defrag)
│   │   ├── coredump/                # Coredump DaemonSet manifest template
│   │   ├── etcd-defrag/             # etcd-defrag CronJob manifest template
│   │   ├── tf/                      # Terraform configurations
│   │   │   ├── coredump/            # Coredump Terraform module
│   │   │   └── etcd-defrag/         # etcd-defrag Terraform module
│   │   ├── .gitlab-ci-coredump.yml  # Generic coredump child pipeline
│   │   └── .gitlab-ci-etcd-defrag.yml # Generic etcd-defrag child pipeline
│   ├── rbac/                        # RBAC configuration
│   └── Helm/
│       ├── tuned/                   # Tuned Helm service
│       └── linuxptp/                # LinuxPTP Helm service
├── retina-cronjobs/                   # Retina cronjobs and management
│   ├── image/                       # Docker image with Python scripts
│   ├── manifests/                   # Kubernetes manifests for cronjobs
│   ├── tf/                          # Terraform for retina-cronjobs deployment
│   ├── registry-credentials/        # Helm chart for registry credentials
│   └── tf-registry-credentials/     # Terraform for registry credentials deployment
├── rbac/                            # RBAC manifest templates
└── scripts/                         # Helper scripts (runner_balancer.py, etc.)
```

## Usage

### 1. Fork ocudu_infra_srs (Public Repo)

This repository is public and contains all the reusable CI/CD templates and configuration generation logic.

```bash
git clone https://gitlab.com/ocudu/ocudu.git
```

### 2. Create Your Private Infrastructure Repository

Create a private repository for your organization that will contain:

- **Cluster definitions** (YAML files describing your infrastructure)
- **Secrets** (tokens, credentials, kubeconfigs)
- **.gitlab-ci.yml** that includes templates from `ocudu_infra_srs`

Directory structure for your private repo:

```text
your-private-infra-repo/
├── .gitlab-ci.yml                      # Triggers CI from ocudu_infra_srs
├── cluster_definition/
│   ├── your_cluster.yaml              # Your cluster definition
│   ├── your_cluster_runners.yaml      # Runner configuration
│   └── your_cluster_services.yaml     # Services configuration
├── secrets/
│   └── gitlab-tokens-your-org.yaml    # GitLab tokens (gitignored!)
└── gitlab-runner/                      # Generated files (artifacts)
    └── your-cluster/
        ├── tf/                         # Generated Terraform
        └── manifests/                  # Generated manifests
```

### 3. Create Cluster Definition Files

Cluster definitions are YAML files that describe your infrastructure.

**Quick overview:**

- **`cluster_definition/your_cluster.yaml`** - Main cluster definition (nodes, resources, global settings)
- **`cluster_definition/your_cluster_runners.yaml`** - GitLab runner configurations
- **`cluster_definition/your_cluster_services.yaml`** - Service configurations (tuned, linuxptp)

**Minimal example:**

```yaml
# your_cluster_runners.yaml
runners:
  worker-node:
    - id: 12345678
      name: glr-build-amd64
      cluster_types: [your-cluster]
      token: glrt-xxxxx
      concurrent: 2
      tags: amd64, build
      cpu_request: 4
      cpu_limit: 4
      memory_request: 8Gi
      memory_limit: 8Gi
      node_tolerations:
      machine=worker-node: NoSchedule
```

### 4. Set Up GitLab CI/CD Variables

In your private repository's CI/CD settings (Settings → CI/CD → Variables), add:

| Variable | Description | Protected | Masked | Used By |
|----------|-------------|-----------|--------|---------|
| `YOUR_KUBECONFIG_VAR` | Kubeconfig for cluster access | ✅ | ❌ | All deployments |
| `YOUR_RUNNER_TOKEN` | GitLab runner registration/update token | ✅ | ✅ | GitLab runner deployment |
| `CODEBOT_USERNAME` | GitLab username for Terraform state backend | ✅ | ❌ | All Terraform jobs |
| `CODEBOT_TOKEN` | GitLab token for Terraform state backend | ✅ | ✅ | All Terraform jobs |
| `REGISTRY_AUTH` | Base64-encoded Docker config JSON for registry authentication | ❌ | ✅ | Registry credentials deployment |
| `GITLAB_REGISTRY_URI` | GitLab container registry URI (e.g., `registry.gitlab.com/your-org`) | ❌ | ❌ | Image builds |

**Note on `REGISTRY_AUTH`**: This variable must contain a base64-encoded Docker config JSON in the format:

```json
{"auths":{"registry.gitlab.com":{"username":"...","password":"...","auth":"..."}}}
```

The variable must **not** be protected so it's available on feature branches during testing.

### 5. Configure Your .gitlab-ci.yml

Use the provided `gitlab-ci.yml.examples` as a starting point. Copy it to your private repo and customize:

```yaml
# .gitlab-ci.yml in your private repo
include:
  - project: ocudu/ocudu
    file: .gitlab/ci-shared/workflow.yml
    ref: dev
  - project: ocudu/ocudu
    file: .gitlab/ci-shared/docker.yml
    ref: dev

stages:
  - child
  - deployer

# Deploy GitLab runners
deploy-gitlab-runners:
  stage: child
  variables:
    CLUSTER_DEF: cluster_definition/your_cluster.yaml
    CLUSTER_TYPE: your-cluster-type
    OUTPUT_DIR: gitlab-runner/your-cluster
    TF_STATE_NAME: helm-your-cluster
    RUNNER_UPDATE_TOKEN_VAR: $YOUR_RUNNER_TOKEN
    RUNNERS_DEF: cluster_definition/your_cluster_runners.yaml
  trigger:
    include:
      - project: ocudu/ocudu
        ref: dev
        file: infrastructure/gitlab-runner/.gitlab-ci.yml
    strategy: depend
```

### 6. Push and Run

Commit your changes and push to GitLab. The CI pipeline will:

1. Clone `ocudu_infra_srs` for templates and scripts
2. Generate cluster-specific Terraform and manifests
3. Validate and plan Terraform changes
4. Apply changes to your cluster (on merge to default branch)

## Key Features

### Artifact-Based Workflow

Generated files are created as CI artifacts and are NOT committed to the repository:

- Terraform files: `*.tf`
- Kubernetes manifests: `*.yaml`

This keeps your repository clean and prevents merge conflicts.

### Multi-Cluster Support

The same CI templates support multiple clusters by passing different variables:

```yaml
parallel:
  matrix:
    - CLUSTER_TYPE: cluster-1
      CLUSTER_DEF: cluster_definition/cluster1.yaml
    - CLUSTER_TYPE: cluster-2
      CLUSTER_DEF: cluster_definition/cluster2.yaml
```

### Secrets Management

All secrets remain in your private repository:

- Kubeconfigs: Stored as CI/CD variables
- GitLab tokens: Stored as CI/CD variables or in `secrets/` (gitignored)
- Registry credentials: Deployed via Helm secrets

### Terraform State

Terraform state is stored in GitLab's HTTP backend:

- Project-specific: State is stored in the running project (your private repo)
- State name: Derived from `TF_STATE_NAME` variable
- Locking: Automatic via GitLab API

## Configuration Generation

The `generate.py` script uses Jinja2 templates to create cluster-specific configurations:

```bash
python3 infrastructure/generator/generate.py \
  cluster_definition/your_cluster.yaml \
  your-cluster-type \
  output-directory \
  --service-def cluster_definition/your_cluster_services.yaml \
  --service-name tuned
```

Templates are located in `infrastructure/generator/templates/`:

- `runner.tf.j2` - GitLab runner Terraform
- `helm_chart.tf.j2` - Helm chart deployments
- `cronjob.yaml.j2` - Kubernetes cronjob manifests

## Testing

### CI Testing

Test CI pipelines on merge requests:

1. Create a branch with changes to cluster definitions
2. Open a merge request
3. CI runs validation and plan stages
4. Review Terraform plan output
5. Manually trigger apply if needed

## Troubleshooting

### Pipeline Fails with "File not found"

Ensure your cluster definition files exist in the private repo:

```bash
cluster_definition/your_cluster.yaml
cluster_definition/your_cluster_runners.yaml
```

### Runner Registration Fails

Check that:

1. `RUNNER_UPDATE_TOKEN_VAR` is set correctly
2. Token has permissions to register runners
3. Cluster can reach gitlab.com

### Generated Files Not Found

Verify:

1. Generate job succeeded
2. Artifacts were created
3. Dependent jobs have `needs: [generate]`

## Contributing

To contribute improvements to the infrastructure automation:

1. Fork `ocudu_infra_srs`
2. Create a feature branch
3. Test changes in your private infrastructure repo
4. Submit a merge request to `ocudu_infra_srs`

## License

This project is part of the OCUDU Infrastructure SRS repository.

## Support

For issues or questions:

- Open an issue in the `ocudu_infra_srs` project
- Contact the infrastructure team
