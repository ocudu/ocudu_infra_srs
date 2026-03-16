# OpenTofu CI Template

`infrastructure/.gitlab-ci.yml` is a generic child-pipeline CI template that runs
`fmt / validate / plan / apply` for any OpenTofu root module in the consumer repository.

## How it works

- The template is included via a `trigger: include:` job in the consumer pipeline.
- `inputs:` carry deployment plumbing: kubeconfig variable name, runner tags, state name, root dir, module source ref.
- Terraform variables (secrets or otherwise) flow as `TF_VAR_*` CI/CD variables set directly on the trigger job — no inputs needed for them.

### Runner and kubeconfig

The input `runner_tags` expects an array of tags applied to the OpenTofu jobs. These jobs need cluster access via the kubeconfig defined in `kubeconfig_var`.

## CI inputs reference

| Input | Default | Description |
| --- | --- | --- |
| `infra_srs_path` | `$CI_PROJECT_NAMESPACE/$CI_PROJECT_NAME` | `infra_srs` repo path (e.g. `ocudu/ocudu_infra_srs`) |
| `infra_srs_ref` | `$CI_COMMIT_REF_NAME` | Branch or tag to source the module from |
| `retina_pypi_index` | `${RETINA_PYPI_INDEX}` | Retina PyPI index URL |
| `retina_registry_uri` | `${RETINA_REGISTRY_URI}` | Retina container registry URI (e.g. `registry.gitlab.com/ocudu/ocudu_infra_srs/retina`) |
| `kubeconfig_var` | required | Name of the **file-type** CI/CD variable holding the kubeconfig |
| `runner_tags` | `[saas-linux-small-amd64]` | Runner tags for jobs needing cluster access |
| `state_name` | `retina-cluster-setup` | Terraform state name — must be unique per deployment |
| `root_dir` | `infrastructure/retina-cluster-setup` | Directory containing the consumer's `main.tf` |

## Consumer trigger job pattern

```yaml
iac:
  trigger:
    include:
      - project: &infra_srs_path ocudu/ocudu_infra_srs
        ref: &infra_srs_ref main
        file: infrastructure/.gitlab-ci.yml
        inputs:
          infra_srs_path: *infra_srs_path
          infra_srs_ref: *infra_srs_ref
          kubeconfig_var: MY_KUBECONFIG        # name of the file-type CI/CD variable
          runner_tags: [my-runner-tag]          # runners with cluster access
          state_name: my-iac                    # unique per deployment
          root_dir: cluster_definition/my-cluster/my-module
    strategy: mirror
  variables:
    TF_VAR_my_secret: $MY_SECRET   # Terraform secrets as TF_VAR_* project variables
```

`retina_pypi_index` and `retina_registry_uri` only need to be passed explicitly for modules that use `retina_version` or `retina_registry_uri` variables (i.e. `retina-cluster-setup`, `retina-cluster-definition`, `retina-cronjobs`). Other modules can omit them; the defaults pick up the CI/CD variables automatically.

## Predefined `TF_VAR_*` variables

The shared template sets the following variables automatically from its inputs, so consumer `main.tf` files can declare them as plain `variable` blocks:

| Variable | Source input |
| --- | --- |
| `infra_srs_path` | `infra_srs_path` |
| `infra_srs_ref` | `infra_srs_ref` |
| `retina_version` | loaded from `retina/version.yml` |
| `retina_registry_uri` | `retina_registry_uri` |

Any additional `TF_VAR_*` set on the trigger job's `variables:` block are also passed through automatically.

## Consumer `main.tf` pattern

```hcl
terraform {
  required_providers {
    helm = { source = "hashicorp/helm"; version = "~> 3.0" }
  }
  backend "http" {}
}

variable "infra_srs_path" { type = string }
variable "infra_srs_ref"  { type = string }

provider "helm" {}  # reads KUBE_CONFIG_PATH env var set by CI

module "my_module" {
  source = "git::https://${var.infra_srs_path}.git//infrastructure/my-module?ref=${var.infra_srs_ref}"
  # ...
}
```
