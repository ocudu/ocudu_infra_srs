# Kubernetes Core Resources - Terraform

This directory contains Terraform configurations for deploying Kubernetes core resources:

- **Coredump cleanup DaemonSet** - Automatically cleans up old coredumps from nodes
- **etcd defragmentation CronJob** - Periodically defrags etcd for cluster health

---

## Overview

These core resources are deployed as Kubernetes manifests using the Terraform `kubernetes_manifest` resource. The manifests are parameterized using `templatefile()`, allowing the same templates to be reused across different clusters by passing cluster-specific values from the parent pipeline.

### Directory Structure

```
infrastructure/k8s/core/
├── coredump/                          # Coredump manifest template
│   └── coredump-cleanup.yml
├── etcd-defrag/                       # etcd-defrag manifest template
│   └── etcd-defrag-cronjob.yaml
├── .gitlab-ci-coredump.yml            # Generic coredump child pipeline
├── .gitlab-ci-etcd-defrag.yml         # Generic etcd-defrag child pipeline
└── tf/                                # Terraform configurations
    ├── coredump/                      # Coredump Terraform module
    │   ├── main.tf
    │   ├── versions.tf
    │   ├── variables.tf
    │   ├── backend.tfbackend
    │   └── coredump.tf
    └── etcd-defrag/                   # etcd-defrag Terraform module
        ├── main.tf
        ├── versions.tf
        ├── variables.tf
        ├── backend.tfbackend
        └── etcd-defrag.tf
```

---

## Resources

### Coredump Cleanup

**Type**: DaemonSet
**Namespace**: Configurable (default: `infra`)
**Terraform Directory**: `tf/coredump/`
**Manifest**: `../coredump/coredump-cleanup.yml`
**Resource Name**: `kubernetes_manifest.coredump_cleanup`

Deploys a DaemonSet that runs on nodes with the `cleanup=true` label. It automatically deletes coredump files older than 7 days from `/mnt/coredump`.

**Template Variables**:
| Variable | Description |
|----------|-------------|
| `namespace` | Kubernetes namespace (default: `infra`) |

### etcd Defragmentation

**Type**: CronJob
**Namespace**: Configurable (default: `infra`)
**Terraform Directory**: `tf/etcd-defrag/`
**Manifest**: `../etcd-defrag/etcd-defrag-cronjob.yaml`
**Resource Name**: `kubernetes_manifest.etcd_defrag`

Deploys a CronJob that periodically defrags etcd to maintain cluster performance. All cluster-specific values (endpoints, certificates, master nodes) are passed as variables.

**Schedule**: Weekly on Sunday at 3:00 AM (`0 3 * * 0`)
**Node Affinity**: Runs only on master nodes

**Template Variables**:
| Variable | Type | Description |
|----------|------|-------------|
| `namespace` | string | Kubernetes namespace (default: `infra`) |
| `master_nodes` | list(string) | Master node hostnames for nodeAffinity scheduling |
| `etcd_endpoints` | string | Comma-separated etcd endpoints |
| `ca_cert_path` | string | Host path to etcd CA certificate |
| `client_cert_path` | string | Host path to etcd client certificate |
| `client_key_path` | string | Host path to etcd client key |

---

## Deployment

### From Private Infrastructure Repository (Cluster Definition)

The deployment is managed through child pipelines triggered from your private infrastructure repository. Each cluster defines its own jobs with cluster-specific variables:

```yaml
# Example: parent jobs in your private .gitlab-ci.yml

k8s-coredump <cluster>:
  stage: child
  variables:
    RUNNER_TAGS: "<runner-tag>"
    KUBECONFIG_VAR_NAME: "<kubeconfig-variable-name>"
    TF_STATE_NAME: "<state-name>"
  trigger:
    include:
      - project: ocudu/ocudu_infra_srs
        ref: main
        file: infrastructure/k8s/core/.gitlab-ci-coredump.yml
    strategy: depend

k8s-etcd-defrag <cluster>:
  stage: child
  variables:
    RUNNER_TAGS: "<runner-tag>"
    KUBECONFIG_VAR_NAME: "<kubeconfig-variable-name>"
    TF_STATE_NAME: "<state-name>"
    TF_DIR: "infrastructure/k8s/core/tf/etcd-defrag"
    TF_VAR_etcd_endpoints: "<endpoints>"
    TF_VAR_master_nodes: '["<node1>", "<node2>"]'
    TF_VAR_ca_cert_path: "<path>"
    TF_VAR_client_cert_path: "<path>"
    TF_VAR_client_key_path: "<path>"
  trigger:
    include:
      - project: ocudu/ocudu_infra_srs
        ref: main
        file: infrastructure/k8s/core/.gitlab-ci-etcd-defrag.yml
    strategy: depend
```

### Required Variables

**Coredump** (`RUNNER_TAGS`, `KUBECONFIG_VAR_NAME`, `TF_STATE_NAME`):
| Variable | Description | Example |
|----------|-------------|---------|
| `RUNNER_TAGS` | GitLab runner tags | `"terraform"` |
| `KUBECONFIG_VAR_NAME` | CI variable name with kubeconfig path | `"RETINA_NAMESPACE_KUBECONFIG"` |
| `TF_STATE_NAME` | Terraform state name | `"k8s-coredump"` |

**etcd-defrag** (all coredump variables plus):
| Variable | Description | Example |
|----------|-------------|---------|
| `TF_DIR` | Terraform directory path | `"infrastructure/k8s/core/tf/etcd-defrag"` |
| `TF_VAR_etcd_endpoints` | etcd endpoints | `"https://10.0.0.1:2379,https://10.0.0.2:2379"` |
| `TF_VAR_master_nodes` | JSON list of master node names | `'["master-0", "master-1"]'` |
| `TF_VAR_ca_cert_path` | Path to CA cert on host | `"/etc/ssl/etcd/ssl/ca.pem"` |
| `TF_VAR_client_cert_path` | Path to client cert on host | `"/etc/ssl/etcd/ssl/node-master.pem"` |
| `TF_VAR_client_key_path` | Path to client key on host | `"/etc/ssl/etcd/ssl/node-master-key.pem"` |

### Child Pipeline Stages

1. `validate` - Format check and Terraform validation (MR only)
2. `plan` - Terraform plan (MR only, saves artifact)
3. `apply` - Terraform apply (MR manual, default branch automatic, scheduled automatic)

---

## Terraform Configuration

### Shared Configuration (all modules)

Each Terraform module (`coredump/`, `etcd-defrag/`) contains:

**`main.tf`**:
```terraform
terraform {
  backend "http" {}
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}
```

**`versions.tf`**:
```terraform
terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.38.0"
    }
  }
  required_version = ">= 1.0.0"
}
```

**`backend.tfbackend`**:
```hcl
lock_method    = "POST"
unlock_method  = "DELETE"
retry_wait_min = 5
```

### Resource-Specific Configuration

**`coredump/coredump.tf`**:
```terraform
resource "kubernetes_manifest" "coredump_cleanup" {
  manifest = yamldecode(
    templatefile("../../coredump/coredump-cleanup.yml", {
      namespace = var.namespace
    })
  )
  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}
```

**`etcd-defrag/etcd-defrag.tf`**:
```terraform
resource "kubernetes_manifest" "etcd_defrag" {
  manifest = yamldecode(
    templatefile("../../etcd-defrag/etcd-defrag-cronjob.yaml", {
      namespace        = var.namespace
      master_nodes     = var.master_nodes
      etcd_endpoints   = var.etcd_endpoints
      ca_cert_path     = var.ca_cert_path
      client_cert_path = var.client_cert_path
      client_key_path  = var.client_key_path
    })
  )
  field_manager {
    name            = "Terraform"
    force_conflicts = true
  }
}
```

---

## Scheduled Deployments

To run all k8s core deployments on a schedule:

1. Go to GitLab UI -> CI/CD -> Schedules -> New schedule
2. **Description**: "Infra Update - Weekly Maintenance" (must start with "Infra Update")
3. **Interval**: Custom (e.g., `0 3 * * 0` for Sunday at 3 AM)
4. **Target branch**: `main`
5. **Save** (no additional variables needed)

Jobs will trigger automatically based on the schedule description regex match.

---

## Manual Deployment

### Manual etcd-defrag Trigger

To manually trigger an etcd-defrag run immediately (without waiting for the weekly schedule):

```bash
kubectl create job --from=cronjob/etcd-defrag etcd-defrag-manual -n infra

# Check status
kubectl get jobs -n infra -w

# View logs
kubectl logs -n infra job/etcd-defrag-manual
```

---

## Troubleshooting

### Error: "resource already exists"

**Cause**: The Kubernetes resource already exists in the cluster but is not tracked in Terraform state.

**Solution**: Delete the old resource and let Terraform recreate it:

```bash
kubectl delete cronjob etcd-defrag -n kube-system
```

### Error: "field manager conflict"

**Cause**: Another tool (e.g., kubectl) previously managed the resource.

**Solution**: The `field_manager` block with `force_conflicts = true` handles this automatically. If issues persist, delete the resource and re-apply.

### Error: "namespaces 'infra' not found"

**Cause**: The `infra` namespace doesn't exist in the cluster.

**Solution**: Create the namespace:
```bash
kubectl create namespace infra
```

### Certificate Mount Failures (etcd-defrag)

**Symptom**: Pods stuck in `ContainerCreating` with errors like:
```
MountVolume.SetUp failed for volume "client-key" : hostPath type check failed:
/etc/ssl/etcd/ssl/node-master-key.pem is not a file
```

**Cause**: The certificate files specified in the variables don't exist on all master nodes.

**Solution**:
1. Check which certificates are available on all master nodes:
   ```bash
   ls /etc/ssl/etcd/ssl/
   ```
2. Update the `TF_VAR_client_cert_path` and `TF_VAR_client_key_path` variables in the cluster definition to use certificates available on all masters.

### Pipeline Job "Empty" Error

**Symptom**: Child pipeline fails with "The resulting pipeline would have been empty"

**Cause**: Child pipeline jobs don't have rules that match the trigger source.

**Solution**: Ensure all apply jobs have:
```yaml
rules:
  - if: $ON_MR
    when: manual
    allow_failure: true
  - if: $ON_DEFAULT_BRANCH
  - if: $CI_PIPELINE_SOURCE == "parent_pipeline"
```

---
