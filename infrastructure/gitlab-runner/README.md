# GitLab Runner Deployment

This directory contains reusable CI/CD templates for deploying GitLab runners using a **generator-based workflow**. Instead of manually maintaining Terraform and Helm configuration files, you define runners in YAML cluster definition files, and the CI pipeline automatically generates and deploys the necessary configurations.

---

## Overview

The GitLab runner deployment follows an artifact-based, template-driven approach:

1. **Define** runners in cluster definition YAML files (in your private infrastructure repository)
2. **Generate** Terraform and Helm configurations using Jinja2 templates
3. **Validate** and **Plan** changes with Terraform
4. **Apply** changes automatically (on default branch) or manually (on merge requests)

**Key Benefits:**
- **No manual `.tf` or manifest editing** - all configuration comes from cluster definition files
- **Artifact-based** - generated files are CI artifacts, not committed to the repository
- **Multi-cluster support** - same templates support different clusters via parameterization
- **Safe deployment** - automatic runner pause/unpause and job cancellation before updates

---

## Architecture

The deployment pipeline consists of the following stages:

```
┌─────────────┐
│  GENERATE   │  Clone ocudu_infra_srs, run generate.py with cluster definitions
└──────┬──────┘
       │ Artifacts: *.tf, *.yaml
       ▼
┌─────────────┐
│  VALIDATE   │  Terraform fmt check, terraform validate
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    PLAN     │  Terraform plan (MR only)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    APPLY    │  Pause runners → Apply changes → Unpause runners
└─────────────┘
```

---

## Usage

### 1. Define Runners in Your Private Repository

In your private infrastructure repository, create or modify cluster definition files:

**File: `cluster_definition/your_cluster_runners.yaml`**

```yaml
runners:
  node-name:
    - id: 12345678                    # GitLab runner ID
      name: glr-my-runner-amd64      # Runner name (becomes Terraform resource name)
      cluster_types:                  # Optional: filter by cluster type
        - your-cluster-type
      token: glrt-xxxxx               # Runner registration token
      concurrent: 2                   # Number of concurrent jobs
      tags: amd64, build             # GitLab runner tags
      cpu_request: 4                  # CPU request
      cpu_limit: 4                    # CPU limit
      memory_request: 8Gi            # Memory request
      memory_limit: 8Gi              # Memory limit
      node_tolerations:               # Node tolerations
      machine=node-name: NoSchedule
```

See the [Cluster Definition Guide](#cluster-definition-guide) below for comprehensive documentation.

### 2. Configure CI/CD in Your Private Repository

In your `.gitlab-ci.yml`, trigger this template:

```yaml
deploy-gitlab-runners:
  stage: child
  variables:
    CLUSTER_DEF: cluster_definition/your_cluster.yaml          # Main cluster definition
    CLUSTER_TYPE: your-cluster-type                           # Cluster type filter
    OUTPUT_DIR: gitlab-runner/your-cluster                    # Output directory for artifacts
    TF_STATE_NAME: helm-your-cluster                          # Terraform state name
    RUNNER_UPDATE_TOKEN_VAR: $YOUR_RUNNER_TOKEN              # Runner token variable
    RUNNERS_DEF: cluster_definition/your_cluster_runners.yaml # Runner definitions
    RUNNER_TAGS: terraform                                    # Tags for CI runner
  trigger:
    include:
      - project: ocudu/ocudu
        ref: dev
        file: infrastructure/gitlab-runner/.gitlab-ci.yml
    strategy: depend
```

### 3. Set CI/CD Variables

In your private repository's CI/CD settings (Settings → CI/CD → Variables):

| Variable | Description | Protected | Masked |
|----------|-------------|-----------|--------|
| `YOUR_KUBECONFIG_VAR` | Kubeconfig for cluster access | ✅ | ❌ |
| `YOUR_RUNNER_TOKEN` | GitLab runner registration/update token | ✅ | ✅ |
| `CODEBOT_USERNAME` | GitLab username for Terraform state backend | ✅ | ❌ |
| `CODEBOT_TOKEN` | GitLab token for Terraform state backend | ✅ | ✅ |

### 4. Push and Deploy

```bash
git checkout main
git pull
git checkout -b update-runners
# Edit cluster_definition/your_cluster_runners.yaml
git add cluster_definition/your_cluster_runners.yaml
git commit -m "Update runner configuration"
git push
```

**On Merge Request:**
- Generate, validate, and plan stages run automatically
- Review Terraform plan output
- Manually trigger `runner-quarantine-apply` to test changes

**On Default Branch (after merge):**
- All stages run automatically
- Runners are paused, updated, and unpaused

---

## Pipeline Stages

### Generate Stage

Clones `ocudu_infra_srs` and runs `generate.py` to create Terraform and Helm configuration files from cluster definitions.

**Artifacts created:**
- `${OUTPUT_DIR}/tf/*.tf` - Terraform files for each runner
- `${OUTPUT_DIR}/manifests/*.yaml` - Helm values files for each runner

### Validate Stage

Runs `terraform fmt -check -diff` and `terraform validate` to ensure generated configurations are correct.

### Plan Stage (MR only)

Runs `terraform plan` to show what changes will be applied. Review the plan output in the CI logs before applying.

### Apply Stage

Runs the `runner-quarantine-apply.sh` script which:

1. Runs `terraform plan -detailed-exitcode` to detect changes
2. If runners changed:
   - **Pauses** affected runners in GitLab
   - **Waits 1 minute** for running jobs to finish
   - **Cancels** any remaining jobs
3. Runs `terraform apply` to update runners
4. **Unpauses** affected runners

This ensures minimal disruption to running CI jobs.

---

## Cluster Definition Guide

See the main [Infrastructure README](../README.md) for comprehensive documentation on creating cluster definitions, including:

- Full runner configuration options
- RBAC configuration
- Node tolerations and affinity
- Resource limits and requests
- Multi-cluster filtering with `cluster_types`

---

## Troubleshooting

### Pipeline Fails: "File not found"

Ensure your cluster definition files exist:
```bash
ls cluster_definition/your_cluster.yaml
ls cluster_definition/your_cluster_runners.yaml
```

### Runner Registration Fails

Check:
1. `RUNNER_UPDATE_TOKEN_VAR` is set correctly in CI/CD variables
2. Token has permissions to register/update runners
3. Cluster has network access to `https://gitlab.com`

### Terraform State Locked

Unlock manually via GitLab API:
```bash
curl --request DELETE --header "PRIVATE-TOKEN: $YOUR_TOKEN" \
  "https://gitlab.com/api/v4/projects/$PROJECT_ID/terraform/state/$TF_STATE_NAME/lock"
```

### Generated Files Not Visible

The generated files are **CI artifacts**, not committed to the repository. To inspect them:
1. Go to the pipeline → `generate` job → "Browse" artifacts
2. Download and review `${OUTPUT_DIR}/tf/*.tf`

---

## Local Testing

Test configuration generation locally before pushing:

```bash
# Clone ocudu
git clone https://gitlab.com/ocudu/ocudu.git

# Generate configurations
python3 ocudu/infrastructure/generator/generate.py \
  cluster_definition/your_cluster_runners.yaml \
  your-cluster-type \
  /tmp/output/tf \
  --repo-root .

# Review generated files
ls /tmp/output/tf/
```

---

## Migration from Manual Configuration

If you're migrating from manually maintained `.tf` and manifest files:

1. **Backup existing configurations** (they will be replaced by generated ones)
2. **Convert to cluster definition format** - extract runner configuration into YAML
3. **Run generate locally** to verify output matches expectations
4. **Test in MR** before merging to default branch
5. **Terraform will handle state migration** automatically if resource names match

---
