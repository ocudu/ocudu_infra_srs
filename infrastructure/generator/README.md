# Infrastructure Generator

This directory contains templates and scripts to generate Terraform and Helm configurations from cluster definition files.

## Structure

- `templates/` - Jinja2 templates for generating configuration files
  - `gitlab-runner/terraform/` - Terraform templates (main.tf.j2, runner.tf.j2)
  - `gitlab-runner/manifests/` - Helm values templates (runner-values.yaml.j2)
- `generate.py` - Main generator script
- `scripts/` - Utility scripts
  - `detect_changes.sh` - Section-aware change detection for CI pipelines
- `.gitlab-ci.yml` - Base CI job definitions for runner pipelines

## Usage

```bash
# Generate for production cluster
python3 generator/generate.py \
  cluster_definition/prod_cluster.yaml \
  prod-cluster \
  gitlab-runner/prod/tf \
  --repo-root .

# Generate for staging cluster
python3 generator/generate.py \
  cluster_definition/staging_cluster.yaml \
  staging-cluster \
  gitlab-runner/staging/tf \
  --repo-root .

# Generate for development cluster
python3 generator/generate.py \
  cluster_definition/dev_cluster.yaml \
  dev-cluster \
  gitlab-runner/dev/tf \
  --repo-root .
```

## Cluster Types

**Cluster types are user-defined** - you choose any name that makes sense for your organization. The generator filters runners based on the `cluster_types` field in runner definitions.

**How It Works:**
- Generator called with `prod-cluster` → includes runners with `cluster_types: ["prod-cluster"]`
- Generator called with `staging-cluster` → includes runners with `cluster_types: ["staging-cluster"]`
- Runners without `cluster_types` field → included in all cluster types (backward compatible)

**Multi-Organization Support:**
Multiple organizations can share the same physical cluster by using different cluster type names. Each organization's runners are filtered by their specific cluster type value.

## Generated Files

The generator creates two types of files:

### Terraform Files (in `gitlab-runner/{cluster}/tf/`)
- `main.tf` - Terraform provider configuration
- `glr-*.tf` - Individual Terraform files for each GitLab runner (matching existing pattern)

### Manifest Files (in `gitlab-runner/{cluster}/manifests/`)
- `glr-*.yaml` - Helm values files for each GitLab runner (used by Terraform Helm releases)

**Note:** The generator only writes these files. Other files like `backend.tfbackend` are preserved and not modified. The generated files replace the existing `glr-*.tf` and manifest files, providing a drop-in replacement.

## How It Works

1. **Reads cluster definition YAML file** - Parses the cluster definition and runner definition files
2. **Filters runners** - Generates configs for all enabled runners that:
   - Have both `id` and `name` defined in the cluster definition's `runners` section
   - Match the specified `cluster_types` (or have no `cluster_types` field)
   - Are not disabled (`enabled: false`)
3. **Extracts runner configuration** - Pulls runner-specific values (token, concurrent, tags, CPU, memory, etc.)
4. **Renders Jinja2 templates** - Uses the `name` field as the Terraform resource name
5. **Outputs generated files**:
   - Terraform files: `main.tf`, `glr-*.tf` (one per runner)
   - Helm values files: `glr-*.yaml` (one per runner)

The cluster definition is the **single source of truth** for all runner configuration.

## Jinja2 Templating System

The generator uses **Jinja2 templates** to transform cluster definition YAML files into Terraform configurations and Helm values files. This provides a flexible, maintainable way to generate infrastructure code from declarative definitions.

### Template Structure

Templates are organized by deployment type:

```
templates/
├── gitlab-runner/
│   ├── terraform/
│   │   ├── main.tf.j2              # Terraform provider configuration
│   │   └── runner.tf.j2            # Individual runner resource template
│   └── manifests/
│       └── runner-values.yaml.j2   # Helm values template for each runner
├── k8s/
│   ├── linuxptp/
│   │   ├── terraform/helm-release.tf.j2
│   │   └── manifests/values.yaml.j2
│   └── tuned/
│       ├── terraform/helm-release.tf.j2
│       └── manifests/values.yaml.j2
```

### How Jinja2 Templates Work

#### 1. Variable Substitution

Templates receive context variables from `generate.py` and substitute them into the output:

**Template (`runner.tf.j2`):**
```terraform
resource "helm_release" "{{ runner.name }}" {
  name       = "{{ runner.name }}"
  namespace  = "gitlab-runner"
  repository = "https://charts.gitlab.io"
  chart      = "gitlab-runner"
  
  values = [
    file("${path.module}/../../manifests/{{ runner.name }}.yaml")
  ]
}
```

**Context provided by `generate.py`:**
```python
{
  "runner": {
    "name": "glr-build-amd64",
    "id": 12345678,
    "token": "glrt-xxxxx",
    # ... more fields
  }
}
```

**Generated output (`glr-build-amd64.tf`):**
```terraform
resource "helm_release" "glr-build-amd64" {
  name       = "glr-build-amd64"
  namespace  = "gitlab-runner"
  repository = "https://charts.gitlab.io"
  chart      = "gitlab-runner"
  
  values = [
    file("${path.module}/../../manifests/glr-build-amd64.yaml")
  ]
}
```

#### 2. Conditional Logic

Templates can include or exclude sections based on context variables:

**Template example:**
```jinja2
{% if runner.rbac %}
  set {
    name  = "rbac.create"
    value = "true"
  }
  {% if runner.rbac.clusterWideAccess %}
  set {
    name  = "rbac.clusterWideAccess"
    value = "true"
  }
  {% endif %}
{% endif %}
```

**Result:** RBAC configuration is only generated when defined in cluster definition.

#### 3. Loops and Iteration

Templates can iterate over lists in the context:

**Template example:**
```jinja2
{% for tag in runner.tags.split(',') %}
    - {{ tag.strip() }}
{% endfor %}
```

**Input:** `runner.tags = "amd64, build, on-prem"`

**Output:**
```yaml
    - amd64
    - build
    - on-prem
```

#### 4. Filters and Functions

Jinja2 provides filters to transform values:

```jinja2
{{ runner.memory_limit | default('8Gi') }}          # Provide default value
{{ runner.name | upper }}                           # Transform to uppercase
{{ runner.tags.split(',') | length }}               # Get list length
```

### Context Variables Available in Templates

The `generate.py` script provides the following context to templates:

#### For GitLab Runner Templates:

| Variable | Description | Example |
|----------|-------------|---------|
| `runner.name` | Runner name (Terraform resource name) | `"glr-build-amd64"` |
| `runner.id` | GitLab runner ID | `12345678` |
| `runner.token` | Runner registration token | `"glrt-xxxxx"` |
| `runner.concurrent` | Concurrent jobs | `2` |
| `runner.tags` | Comma-separated tags | `"amd64, build"` |
| `runner.cpu_request` | CPU request | `4` |
| `runner.cpu_limit` | CPU limit | `4` |
| `runner.memory_request` | Memory request | `"8Gi"` |
| `runner.memory_limit` | Memory limit | `"8Gi"` |
| `runner.node_tolerations` | Dict of tolerations | `{"machine=node1": "NoSchedule"}` |
| `runner.rbac` | RBAC configuration | `{"clusterWideAccess": true, "rules": [...]}` |
| `runner.service_account` | Service account name | `"glr-build-amd64-gitlab-runner"` |
| `global.gitlab_runner.*` | Global runner settings (image, cache, etc.) | From cluster definition |

### Template Rendering Process

```
┌──────────────────────┐
│ Cluster Definition   │
│   (YAML)            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   generate.py        │
│  - Parse YAML        │
│  - Filter runners    │
│  - Build context     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Jinja2 Template     │
│   (.j2 files)        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Generated Files     │
│  (.tf, .yaml)        │
└──────────────────────┘
```

### Example: Complete Runner Template Flow

**Input: `cluster_definition/lab_cluster_runners.yaml`**
```yaml
runners:
  retina-e2e:
    - id: 43853548
      name: glr-e2e-amd64
      cluster_types: ["lab"]
      token: glrt-xxxxx
      concurrent: 4
      tags: retina-e2e-amd64
      cpu_request: 1
      cpu_limit: 2
      memory_request: 3Gi
      memory_limit: 3Gi
      node_tolerations:
        purpose=retina-e2e: NoSchedule
      service_account: glr-e2e-amd64-gitlab-runner
      rbac:
        clusterWideAccess: true
        rules:
          - apiGroups: [""]
            resources: ["pods", "secrets"]
            verbs: ["get", "list", "create"]
```

**Template: `templates/gitlab-runner/terraform/runner.tf.j2`** (simplified)
```jinja2
resource "helm_release" "{{ runner.name }}" {
  name      = "{{ runner.name }}"
  namespace = "gitlab-runner"
  chart     = "gitlab-runner"
  
  values = [
    file("${path.module}/../../manifests/{{ runner.name }}.yaml")
  ]
  
  {% if runner.service_account %}
  set {
    name  = "serviceAccount.name"
    value = "{{ runner.service_account }}"
  }
  {% endif %}
}
```

**Output: `gitlab-runner/lab/tf/glr-e2e-amd64.tf`**
```terraform
resource "helm_release" "glr-e2e-amd64" {
  name      = "glr-e2e-amd64"
  namespace = "gitlab-runner"
  chart     = "gitlab-runner"
  
  values = [
    file("${path.module}/../../manifests/glr-e2e-amd64.yaml")
  ]
  
  set {
    name  = "serviceAccount.name"
    value = "glr-e2e-amd64-gitlab-runner"
  }
}
```

### Adding New Templates

To add support for a new resource type:

1. **Create template directory** under `templates/`:
   ```bash
   mkdir -p templates/new-resource/terraform
   mkdir -p templates/new-resource/manifests
   ```

2. **Create Jinja2 templates**:
   - `templates/new-resource/terraform/*.tf.j2`
   - `templates/new-resource/manifests/*.yaml.j2`

3. **Update `generate.py`** to:
   - Parse new resource definitions from cluster definition
   - Build appropriate context variables
   - Render new templates

4. **Test locally**:
   ```bash
   python3 generate.py test_cluster.yaml test-type /tmp/output --repo-root .
   ```

### Debugging Templates

To debug template rendering:

1. **Add print statements in `generate.py`**:
   ```python
   print(f"Context for {runner['name']}: {context}")
   ```

2. **Check generated output** in CI artifacts or local `/tmp/output`

3. **Validate Jinja2 syntax** with test renders:
   ```python
   from jinja2 import Template
   template = Template("{{ runner.name }}")
   print(template.render(runner={"name": "test"}))
   ```

## CI/CD Integration

The generator is integrated into GitLab CI pipelines:

- **Generation stage**: Runs `generate.py` to create Terraform and manifest files
- **Change detection**: Uses `scripts/detect_changes.sh` to detect if runner-related sections changed
- **Base jobs**: Defined in `.gitlab-ci.yml` and extended by individual pipeline configs

See `generator/scripts/README.md` for details on change detection.

