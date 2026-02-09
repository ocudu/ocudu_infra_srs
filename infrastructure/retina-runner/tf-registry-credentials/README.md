# Registry Credentials Deployment

This directory contains Terraform configuration for deploying Docker registry credentials across multiple Kubernetes namespaces using a Helm chart.

---

## Overview

The registry credentials deployment creates Kubernetes `dockerconfigjson` secrets in specified namespaces, allowing pods to pull images from private container registries (e.g., GitLab Container Registry).

**Purpose:**
- Deploy registry authentication credentials to multiple namespaces in a single operation
- Use Terraform to manage the lifecycle of registry credential secrets
- Support multiple clusters with different namespace configurations

---

## Architecture

```
┌─────────────────────────────────────┐
│  Private Infrastructure Repo        │
│  .gitlab-ci.yml                     │
│  - Triggers deployment              │
│  - Passes REGISTRY_AUTH variable    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  ocudu_infra_srs (Public Repo)      │
│  tf-registry-credentials/           │
│  ├── .gitlab-ci.yml                 │
│  ├── main.tf                        │
│  └── ../registry-credentials/       │
│      ├── Chart.yaml                 │
│      ├── values.yaml                │
│      └── templates/secret.yaml      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Kubernetes Cluster                 │
│  ├── namespace: infrastructure      │
│  │   └── Secret: registry-credentials
│  ├── namespace: retina              │
│  │   └── Secret: registry-credentials
│  └── namespace: infra               │
│      └── Secret: registry-credentials
└─────────────────────────────────────┘
```

---

## Deployment

### From Private Infrastructure Repository

In your private infrastructure repository's `.gitlab-ci.yml`, trigger this deployment:

```yaml
opentofu deploy registry-credentials lab:
  stage: deployer
  variables:
    KUBECONFIG_VAR_NAME: KUBECONFIG_LAB
    GITLAB_TOFU_STATE_NAME: terraform-registry-credentials-lab
    NAMESPACES: '["infrastructure", "retina"]'
    REGISTRY_AUTH: $REGISTRY_AUTH  # Forward project-level variable
  trigger:
    include:
      - project: ocudu/ocudu
        ref: dev
        file: infrastructure/retina-runner/tf-registry-credentials/.gitlab-ci.yml
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
| `GITLAB_TOFU_STATE_NAME` | Terraform state name for this deployment | `terraform-registry-credentials-lab` |
| `NAMESPACES` | JSON array of namespaces to deploy credentials to | `'["infrastructure", "retina"]'` |
| `REGISTRY_AUTH` | Base64-encoded Docker config JSON | `$(base64 auth.json)` |

### REGISTRY_AUTH Format

The `REGISTRY_AUTH` variable must contain a **base64-encoded** Docker config JSON:

**Example `auth.json` (before encoding):**
```json
{
  "auths": {
    "registry.gitlab.com": {
      "username": "gitlab-user",
      "password": "glpat-xxxxx",
      "auth": "Z2l0bGFiLXVzZXI6Z2xwYXQteHh4eHg="
    }
  }
}
```

**Encode to base64:**
```bash
cat auth.json | base64 -w 0
```

**Set as GitLab CI/CD variable:**
- Go to Settings → CI/CD → Variables
- Name: `REGISTRY_AUTH`
- Value: `<base64-encoded JSON>`
- Protected: ❌ (must be available on feature branches for testing)
- Masked: ✅

---

## Terraform Configuration

### `main.tf`

The Terraform configuration deploys the Helm chart to each namespace specified in the `NAMESPACES` variable.

**Key features:**
- Uses `for_each` to iterate over namespaces
- Deploys the same Helm chart to each namespace independently
- Passes `authToken` (base64-encoded Docker config) to the Helm chart
- Uses GitLab HTTP backend for state management

**Resource structure:**
```terraform
resource "helm_release" "registry-credentials" {
  for_each = toset(var.namespaces)
  
  name      = "registry-credentials"
  namespace = each.value
  chart     = "../registry-credentials/"
  
  set_sensitive {
    name  = "authToken"
    value = var.authToken
  }
}
```

### Variables

| Variable | Type | Description |
|----------|------|-------------|
| `kubeconfig` | `string` | Path to kubeconfig file (set by CI) |
| `authToken` | `string` | Base64-encoded Docker config JSON |
| `namespaces` | `list(string)` | List of namespaces to deploy credentials to |

---

## Helm Chart: registry-credentials

The Helm chart creates Kubernetes `dockerconfigjson` secrets in each specified namespace.

### Chart Files

- **`Chart.yaml`** - Chart metadata (name, version, description)
- **`values.yaml`** - Default values (overridden by Terraform `set` blocks)
- **`templates/secret.yaml`** - Secret resource template

### `templates/secret.yaml`

```yaml
{{- range $.Values.namespaces }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ $.Values.secretName }}
  namespace: {{ . }}
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: {{ $.Values.authToken | quote }}
{{- end }}
```

**Important:**
- `authToken` is **already base64-encoded** when passed from `REGISTRY_AUTH`
- The template does **not** re-encode it (no `| b64enc` filter)
- The secret is created in each namespace specified in the `namespaces` list

### Values

| Value | Description | Set By |
|-------|-------------|--------|
| `authToken` | Base64-encoded Docker config JSON | Terraform (`set_sensitive`) |
| `namespaces` | List of namespaces | Terraform (`set_list`) |
| `secretName` | Name of the secret | `values.yaml` (default: `registry-credentials`) |

---

## CI/CD Pipeline

The `.gitlab-ci.yml` in this directory defines the deployment pipeline.

### Pipeline Stages

1. **Preparation (`before_script`)**
   - Clone `ocudu_infra_srs` for Terraform and Helm chart files
   - Copy `tf-registry-credentials/` and `registry-credentials/` to working directory
   - Set `TF_VAR_authToken` from `REGISTRY_AUTH` CI variable

2. **OpenTofu Init, Plan, Apply**
   - Uses `gitlab-tofu` templates from `gitlab.com/components/opentofu/job-templates`
   - Manages Terraform state in GitLab HTTP backend
   - Validates, plans, and applies infrastructure changes

### Key Configuration

```yaml
include:
  - component: gitlab.com/components/opentofu/job-templates@3.11.0
    inputs:
      opentofu_version: 1.10.6
      state_name: ${GITLAB_TOFU_STATE_NAME}
      working_directory: infrastructure/retina-runner/tf-registry-credentials
      tf_var_files: []

before_script:
  - git clone --depth 1 --branch ${OCUDU_BRANCH:-main} https://gitlab.com/ocudu/ocudu.git /tmp/ocudu_infra_srs
  - mkdir -p infrastructure/retina-runner
  - cp -r /tmp/ocudu_infra_srs/infrastructure/retina-runner/tf-registry-credentials infrastructure/retina-runner/
  - cp -r /tmp/ocudu_infra_srs/infrastructure/retina-runner/registry-credentials infrastructure/retina-runner/
  - export TF_VAR_authToken="${REGISTRY_AUTH}"
  - eval K_PATH="\$$KUBECONFIG_VAR_NAME"
  - export TF_VAR_kubeconfig="${K_PATH}"
  - export TF_VAR_namespaces="${NAMESPACES}"
```

---

## Usage Examples

### Deploy to Lab Cluster

```yaml
opentofu deploy registry-credentials lab:
  stage: deployer
  variables:
    KUBECONFIG_VAR_NAME: KUBECONFIG_LAB
    GITLAB_TOFU_STATE_NAME: terraform-registry-credentials-lab
    NAMESPACES: '["infrastructure", "retina"]'
    REGISTRY_AUTH: $REGISTRY_AUTH
  trigger:
    include:
      - project: ocudu/ocudu
        ref: dev
        file: infrastructure/retina-runner/tf-registry-credentials/.gitlab-ci.yml
    strategy: depend
```

### Deploy to Datacenter Cluster

```yaml
opentofu deploy registry-credentials dc:
  stage: deployer
  variables:
    KUBECONFIG_VAR_NAME: KUBECONFIG_DC
    GITLAB_TOFU_STATE_NAME: terraform-registry-credentials-dc
    NAMESPACES: '["infra", "retina"]'
    REGISTRY_AUTH: $REGISTRY_AUTH
  trigger:
    include:
      - project: ocudu/ocudu
        ref: dev
        file: infrastructure/retina-runner/tf-registry-credentials/.gitlab-ci.yml
    strategy: depend
```

### Multiple Namespaces

```yaml
variables:
  NAMESPACES: '["infrastructure", "retina", "gitlab-runner", "monitoring"]'
```

---

## Troubleshooting

### Error: "Secret is invalid: data[.dockerconfigjson]: Invalid value: unexpected end of JSON input"

**Cause:** `REGISTRY_AUTH` variable is empty or malformed.

**Solutions:**
1. Verify `REGISTRY_AUTH` is set in CI/CD variables
2. Ensure `REGISTRY_AUTH` is **not protected** (must be available on feature branches)
3. Check that `REGISTRY_AUTH` is correctly base64-encoded:
   ```bash
   echo "$REGISTRY_AUTH" | base64 -d | jq .
   ```
4. Verify the variable is correctly forwarded in the trigger:
   ```yaml
   variables:
     REGISTRY_AUTH: $REGISTRY_AUTH  # Explicitly forward
   ```

### Error: "cannot re-use a name that is still in use"

**Cause:** Helm releases with the same name already exist in the cluster, but Terraform state doesn't track them.

**Solutions:**
1. Delete existing Helm releases manually:
   ```bash
   kubectl delete secret registry-credentials -n infrastructure
   kubectl delete secret registry-credentials -n retina
   ```
2. Re-run the pipeline to recreate the secrets via Terraform

### Error: "Saved plan is stale"

**Cause:** Terraform state was modified between `plan` and `apply` stages.

**Solution:**
1. Re-run the `plan` job to generate a fresh plan
2. Ensure no manual changes are made to the cluster during pipeline execution

### Error: "This job is waiting for resource: terraform-registry-credentials-X"

**Cause:** Terraform state is locked from a previous pipeline.

**Solution:**
Unlock the state manually via GitLab API:
```bash
curl --request DELETE \
  --header "PRIVATE-TOKEN: $YOUR_GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/projects/$PROJECT_ID/terraform/state/terraform-registry-credentials-X/lock"
```

Replace:
- `$YOUR_GITLAB_TOKEN` with your GitLab personal access token
- `$PROJECT_ID` with your project ID
- `terraform-registry-credentials-X` with the actual state name

---

## Verifying Deployment

After successful deployment, verify the secrets were created:

```bash
# List secrets in each namespace
kubectl get secret registry-credentials -n infrastructure
kubectl get secret registry-credentials -n retina

# View secret details (without decoding)
kubectl describe secret registry-credentials -n infrastructure

# Decode and verify secret content
kubectl get secret registry-credentials -n infrastructure -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq .
```

**Expected output:**
```json
{
  "auths": {
    "registry.gitlab.com": {
      "username": "gitlab-user",
      "password": "glpat-xxxxx",
      "auth": "Z2l0bGFiLXVzZXI6Z2xwYXQteHh4eHg="
    }
  }
}
```

---

## Updating Credentials

To update registry credentials:

1. **Update `REGISTRY_AUTH` variable** in GitLab CI/CD settings with new base64-encoded credentials
2. **Re-run the pipeline** - Terraform will detect the change and update the secrets
3. **Restart pods** that use the credentials (if needed):
   ```bash
   kubectl rollout restart deployment <deployment-name> -n <namespace>
   ```

---

## Design Rationale

### Why Terraform + Helm?

- **Terraform** provides state management and idempotent deployments
- **Helm** simplifies multi-namespace secret creation with templating
- **Combined** approach allows version-controlled, reproducible deployments

### Why `for_each` instead of multiple resources?

- **Scalability**: Easy to add/remove namespaces by modifying the `NAMESPACES` variable
- **DRY principle**: Single resource definition for all namespaces
- **State management**: Each namespace gets its own Terraform state entry (`helm_release.registry-credentials["infrastructure"]`, etc.)

### Why base64-encode in CI variable instead of Helm template?

- **Security**: Avoids exposing raw credentials in Terraform state or Helm values
- **Compatibility**: Kubernetes `dockerconfigjson` secrets expect base64-encoded data
- **Simplicity**: Encoding once in CI variable setup is clearer than template-based encoding

---
