# Retina Cluster Setup

Terraform module that provisions the Kubernetes resources required to run Retina on a cluster.

## Resources managed

| Resource | Description |
| --- | --- |
| `kubernetes_namespace` | Namespace for Retina (default: `retina`) |
| `kubernetes_secret` (docker-registry) | Registry pull-secret, deployed to each namespace in `registry_secret_namespaces` |
| `kubernetes_priority_class` | PriorityClasses defined in `priority_classes`; defaults to `retina-e2e-priority` (value `1000000`) |
| `kubernetes_cluster_role` / `kubernetes_cluster_role_binding` | Read access to nodes, pods, and priorityclasses cluster-wide |
| `kubernetes_role` / `kubernetes_role_binding` | Pod/exec/secret/configmap access in the Retina namespace |

RBAC resources can be disabled with `enable_rbac = false`.

## Inputs

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `namespace` | `string` | `"retina"` | Kubernetes namespace to create |
| `registry_auth` | `string` | required | Base64-encoded `username:token` for the registry |
| `registry_server` | `string` | `"registry.gitlab.com"` | Registry hostname |
| `registry_secret_namespaces` | `list(string)` | `["retina"]` | Namespaces to deploy the pull-secret to |
| `priority_classes` | `map(object)` | `retina-e2e-priority` at `1000000` | PriorityClasses to create |
| `enable_rbac` | `bool` | `true` | Create ClusterRole/ClusterRoleBinding/Role/RoleBinding |

### `priority_classes` object schema

```hcl
map(object({
  value          = number
  description    = string
  global_default = optional(bool, false)
}))
```

Example — add a second class alongside the default:

```hcl
priority_classes = {
  retina-e2e-priority = {
    value       = 1000000
    description = "This priority class should be used for retina service pods only!"
  }
  gitlab-runner-priority = {
    value       = 500000
    description = "Priority class for GitLab runner pods"
  }
}
```

## Using this module

Each cluster needs its own directory with a `main.tf` in the consumer repository.

### `main.tf`

```hcl
terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.0"
    }
  }
  backend "http" {}
}

variable "infra_srs_path" { type = string }
variable "infra_srs_ref" { type = string }
variable "registry_auth" {
  type      = string
  sensitive = true
}

provider "kubernetes" {}

module "retina_cluster_setup" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/retina-cluster-setup?ref=${var.infra_srs_ref}"

  registry_auth              = var.registry_auth
  registry_secret_namespaces = ["retina", "namespace-a"] # adjust per cluster
}
```

If resources already exist in the cluster and need to be imported into state, add import blocks after the module call.

For CI usage see [infrastructure/opentofu.md](../opentofu.md).
