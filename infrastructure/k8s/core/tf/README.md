# Kubernetes Core Resources - Terraform

This directory contains Terraform configurations for deploying Kubernetes core resources:

- **Coredump cleanup cronjob** - Automatically cleans up coredumps from nodes
- **etcd defragmentation cronjob** - Periodically defrags etcd for cluster health

---

## Overview

These core resources are deployed as Kubernetes manifests using the Terraform `kubernetes_manifest` resource. The manifests are stored in `../coredump/` and `../etcd-defrag/` directories and applied via Terraform for state management.

---

## Resources

### Coredump Cleanup

**File**: `coredump.tf`

Deploys a Kubernetes cronjob that cleans up coredumps from cluster nodes.

**Manifest**: `../coredump/coredump-cleanup.yml`

**Apply target**: `kubernetes_manifest.coredump_cleanup`

### etcd Defragmentation

**File**: `etcd-defrag.tf`

Deploys a Kubernetes cronjob that periodically defrags etcd to maintain cluster performance.

**Manifests**:
- `../etcd-defrag/etcd-defrag-cronjob-lab.yaml` (for lab cluster)
- `../etcd-defrag/etcd-defrag-cronjob-datacenter.yaml` (for datacenter cluster)

**Apply target**: `kubernetes_manifest.etcd_defrag` (variable: `$RESOURCE`)

---

## Deployment

### From Private Infrastructure Repository

In your private infrastructure repository's `.gitlab-ci.yml`, trigger this deployment:

```yaml
deploy-k8s-core lab:
  stage: deployer
  variables:
    KUBECONFIG_VAR_NAME: KUBECONFIG_LAB
    TF_STATE_NAME: k8s-core-lab
    RUNNER_TAGS: terraform
    RESOURCE: kubernetes_manifest.etcd_defrag  # For etcd-defrag
  trigger:
    include:
      - project: ocudu/ocudu
        ref: dev
        file: infrastructure/k8s/core/.gitlab-ci.yml
    strategy: depend
  rules:
    - if: $ON_MR
      when: manual
    - if: $ON_DEFAULT_BRANCH
```

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `KUBECONFIG_VAR_NAME` | Name of the CI variable containing kubeconfig | `KUBECONFIG_LAB` |
| `TF_STATE_NAME` | Terraform state name | `k8s-core-lab` |
| `RUNNER_TAGS` | GitLab runner tags | `terraform` |
| `RESOURCE` | Terraform resource to apply (for etcd-defrag) | `kubernetes_manifest.etcd_defrag` |

---

## Pipeline Stages

### Validate Stage

- **`check-format`**: Runs `terraform fmt -check` to verify formatting
- **`validate`**: Runs `terraform validate` to verify configuration

### Apply Stage

- **`apply-coredump`**: Applies the coredump cleanup cronjob
  - Manual on merge requests
  - Automatic on default branch

- **`apply-etcd-defrag`**: Applies the etcd defragmentation cronjob
  - Automatic on default branch
  - Requires `$RESOURCE` variable

- **`import-etcd-defrag`**: Imports existing etcd-defrag cronjob into Terraform state
  - Manual only (for initial setup)
  - Use when migrating existing resources to Terraform

---

## Terraform Configuration

### `main.tf`

Defines providers and backend configuration.

```terraform
terraform {
  backend "http" {}
  
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}
```

### `coredump.tf`

```terraform
resource "kubernetes_manifest" "coredump_cleanup" {
  manifest = yamldecode(
    file("../coredump/coredump-cleanup.yml")
  )
  
  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}
```

### `etcd-defrag.tf`

```terraform
resource "kubernetes_manifest" "etcd_defrag" {
  manifest = yamldecode(
    file("../etcd-defrag/etcd-defrag-cronjob-lab.yaml")  # Or datacenter variant
  )
  
  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}
```

---

## Usage

### Deploy Coredump Cleanup Only

```yaml
apply-coredump:
  script:
    - terraform apply -auto-approve -target=kubernetes_manifest.coredump_cleanup
```

### Deploy etcd Defragmentation Only

```yaml
apply-etcd-defrag:
  variables:
    RESOURCE: kubernetes_manifest.etcd_defrag
  script:
    - terraform apply -auto-approve -target=$RESOURCE
```

### Import Existing etcd-defrag Cronjob

If you have an existing etcd-defrag cronjob in your cluster that you want to manage with Terraform:

```yaml
import-etcd-defrag:
  variables:
    RESOURCE: kubernetes_manifest.etcd_defrag
  script:
    - terraform import $RESOURCE "apiVersion=batch/v1,kind=CronJob,namespace=kube-system,name=etcd-defrag"
```

---

## Customization

### Different Manifests per Cluster

To use different manifests for different clusters (e.g., lab vs datacenter):

1. Store manifests in separate files:
   ```
   etcd-defrag/
   ├── etcd-defrag-cronjob-lab.yaml
   └── etcd-defrag-cronjob-datacenter.yaml
   ```

2. Modify `etcd-defrag.tf` to use the appropriate manifest based on a variable:
   ```terraform
   variable "cluster_type" {
     type    = string
     default = "lab"
   }
   
   resource "kubernetes_manifest" "etcd_defrag" {
     manifest = yamldecode(
       file("../etcd-defrag/etcd-defrag-cronjob-${var.cluster_type}.yaml")
     )
   }
   ```

3. Pass `TF_VAR_cluster_type` in CI:
   ```yaml
   variables:
     TF_VAR_cluster_type: datacenter
   ```

---

## Troubleshooting

### Error: "resource already exists"

**Cause**: The Kubernetes resource already exists in the cluster but is not tracked in Terraform state.

**Solution**: Import the existing resource:
```bash
terraform import kubernetes_manifest.coredump_cleanup \
  "apiVersion=batch/v1,kind=CronJob,namespace=default,name=coredump-cleanup"
```

### Error: "field manager conflict"

**Cause**: Another tool (e.g., kubectl) previously managed the resource.

**Solution**: The `field_manager` block with `force_conflicts = true` in the Terraform configuration should handle this automatically. If issues persist, manually delete the resource and let Terraform recreate it.

### Manifest Changes Not Applied

**Cause**: Terraform doesn't automatically detect changes in manifest files referenced via `file()`.

**Solution**:
1. Use `terraform taint` to force recreation:
   ```bash
   terraform taint kubernetes_manifest.coredump_cleanup
   terraform apply
   ```
2. Or manually delete the resource and re-apply:
   ```bash
   kubectl delete cronjob coredump-cleanup
   terraform apply
   ```

---
