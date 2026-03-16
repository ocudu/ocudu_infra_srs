# Retina Cluster Definition

Terraform module that creates and maintains the `retina-info` ConfigMap in a Kubernetes cluster. The ConfigMap carries cluster topology data (nodes, cluster resources, global settings) that the Retina test framework reads at runtime.

Check the [documentation](../../retina/_docs/02_cluster_setup.md#cluster-definition) for more details.

> **Requirement:** `python3` with `pyyaml` and `jsonchema` libraries must be available in the environment. `kubernetes` python library is mandatory to run the retina_deploy_definition.py script standalone, outside this module.

## Resources managed

| Resource | Description |
| --- | --- |
| `kubernetes_config_map_v1` | `retina-info` ConfigMap in the Retina namespace |

## Inputs

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `cluster_config_path` | `string` | required | Absolute path to the cluster YAML file |
| `namespace` | `string` | `"retina"` | Namespace where the ConfigMap is created |

## ConfigMap fields

| Key | Value |
| --- | --- |
| `version` | `global.version` from the cluster YAML |
| `networking-mode` | `global.networking-mode` |
| `dnsPolicy` | `global.dnsPolicy` (defaults to `ClusterFirst` if absent) |
| `resource` | Base64-encoded JSON of the `nodes` array |
| `cluster_resource_list` | Base64-encoded JSON of the `cluster_resource_list` array |
| `cluster-hash` | SHA-256 of the cluster YAML file — changes when the file changes |

## Using this module

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

provider "kubernetes" {}

module "retina_cluster_definition" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/retina-cluster-definition?ref=${var.infra_srs_ref}"

  cluster_config_path = abspath("${path.module}/lab_cluster.yaml")
}
```

Use `abspath("${path.module}/...")` so the path is valid when passed to the external script.

If the ConfigMap already exists and needs to be imported into state:

```hcl
import {
  to = module.retina_cluster_definition.kubernetes_config_map_v1.retina_info
  id = "retina/retina-info"
}
```

For CI usage see [opentofu.md](../_docs/04_opentofu.md).

## Deploying without IaC

The script deploys the ConfigMap directly using the Kubernetes Python client:

```bash
# pip3 install -r scripts/requirements.txt
python3 scripts/retina_deploy_definition.py path/to/lab_cluster.yaml
```
