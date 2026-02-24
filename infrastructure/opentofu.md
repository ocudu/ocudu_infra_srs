# OpenTofu CI template

`infrastructure/.gitlab-ci.yml` is a generic child-pipeline CI template that runs
`fmt / validate / plan / apply` for any OpenTofu root module in the consumer repository.

## How it works

- The template is included via a `trigger: include:` job in the consumer pipeline.
- `inputs:` carry deployment plumbing: kubeconfig variable name, runner tags, state name,
  root dir, module source ref.
- Terraform variables (secrets or otherwise) flow as `TF_VAR_*` CI/CD variables set
  directly on the trigger job — no inputs needed for them.

## CI inputs reference

| Input | Default | Description |
| --- | --- | --- |
| `infra_srs_path` | `$CI_PROJECT_NAMESPACE/$CI_PROJECT_NAME` | `infra_srs` repo path (e.g. `ocudu/ocudu_infra_srs`) |
| `infra_srs_ref` | `$CI_COMMIT_REF_NAME` | Branch or tag to source the module from |
| `retina_pypi_index` | `${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/pypi` | Retina pypi index |
| `kubeconfig_var` | required | Name of the **file-type** CI/CD variable holding the kubeconfig |
| `runner_tags` | `[saas-linux-small-amd64]` | Runner tags with cluster access |
| `state_name` | `retina-cluster-setup` | Terraform state name — unique per deployment |
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
          retina_pypi_index: https://gitlab.com/api/v4/projects/78028160/packages/pypi/simple
          kubeconfig_var: MY_KUBECONFIG   # name of the file-type CI/CD variable
          runner_tags: [my-runner-tag]    # runners with cluster access
          state_name: my-iac
          root_dir: cluster_def           # Folder for your main.tf
    strategy: mirror
  variables:
    TF_VAR_registry_auth: $REGISTRY_AUTH  # Terraform secrets as TF_VAR_* project variables
    ...
```

Any `TF_VAR_*` variable set in `variables:` on the trigger job is automatically picked up by OpenTofu as the corresponding `var.*` input.
