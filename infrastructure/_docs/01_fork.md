# Fork the Repository

Create your own copy of this repository to customize it for your infrastructure:

```bash
# Clone your forked repository
git clone https://gitlab.com/your_user_or_group/ocudu_infra_srs.git
cd ocudu_infra_srs
```

**Note:** If you also want to fork OCUDU itself, follow the [OCUDU fork setup guide](https://gitlab.com/ocudu/ocudu/-/blob/dev/.gitlab/README.md) or see the [OCUDU documentation](https://ocudu.gitlab.io/ocudu_docs).

## 1. Basic CI/CD Configuration

This repository's CI/CD is configured to access OCUDU from a repository **in the same GitLab instance**. Cross-instance configuration (having `ocudu_infra_srs` in a different GitLab instance than `ocudu`) is not currently supported.

**Default configuration:**

- Expects OCUDU repository at path: `ocudu/ocudu`
- Uses default branch references

**To customize:**

1. Edit [.gitlab-ci.yml](../../.gitlab-ci.yml) and modify the `spec`/`inputs` section to change the default `ocudu_path` and `ocudu_ref`

2. Configure `OCUDU_*` variables as GitLab CI/CD variables:
   - These variables must be accessible from the `ocudu_infra_srs` repository
   - Set them at the **Group level** (recommended for shared access) or in both projects
   - See OCUDU's [CI/CD configuration guide](https://gitlab.com/ocudu/ocudu/-/blob/dev/.gitlab/README.md#21-configure-cicd-variables) for variable details

## 2. Configure the GitLab Project

### GitOps

This repository uses a Terraform/OpenTofu solution to configure the GitLab project itself, including project settings, pipeline schedules, protected branches, approval rules, and more.

**Setup:**

1. Create a CI/CD variable called `GITLAB_TOKEN`:
   - Type: Project Access Token or Personal Access Token
   - Role: `Maintainer`
   - Scopes: `api`, `read_user`, `read_repository`, `write_repository`

2. Modify [.gitlab/main.tf](../../.gitlab/main.tf) according to your needs

3. Commit to main branch (via MR or directly)

For more details, see the [Terraform module documentation](https://gitlab.com/ocudu/ocudu/-/blob/dev/.gitlab/ci-shared/gitlab_settings/README.md).

### Manual

If you don't create the `GITLAB_TOKEN` CI variable, GitOps won't be used and you can manage configuration manually.

Check the scheduled pipelines defined at the end of [.gitlab/main.tf](../../.gitlab/main.tf) to replicate them manually in your project's **Settings → CI/CD → Schedules**.

## 3. E2E Testing Variables

- [Amarisoft ZMQ Configuration](../../e2e/README.md#prerequisites)
- [FTP Server Configuration](../../templates/README.md#ftp-server-configuration)

## 4. Retina CI/CD Configuration

The Retina framework runs in containers during test execution. When you modify Retina code in your fork, the CI/CD pipeline automatically:

- Runs tests to verify the changes
- Builds Python packages and publishes them to a PyPI registry
- Builds container images and pushes them to a container registry
- E2E tests automatically use these container images

You can configure this behavior based on your needs.

### Option A: Skip Retina CI/CD (For Users Not Modifying Retina)

If you're not interested in modifying or building Retina components, you can skip the entire Retina CI/CD pipeline.

In your GitLab project, go to **Settings → CI/CD → Variables** and add:

| Variable | Value | Description |
|----------|-------|-------------|
| `SKIP_RETINA_CI` | `true` | Disables Retina building pipelines |

**Important:** If you skip the Retina CI/CD, you **must** configure your fork to pull pre-built images from an external registry:

| Variable | Value | Example |
|----------|-------|---------|
| `RETINA_REGISTRY_URI` | External container registry path | `registry.gitlab.com/ocudu/ocudu_infra_srs/retina` |
| `DOCKER_AUTH_CONFIG` | Authentication configuration | See below |

If the external registry is private, configure `DOCKER_AUTH_CONFIG`:

```json
{
  "auths": {
    "registry.gitlab.com": {
      "auth": "<base64(username:token)>"
    }
  }
}
```

To generate the base64 encoded auth string:

```bash
echo -n "username:token" | base64
```

For GitLab Container Registry, create a [Deploy Token](https://docs.gitlab.com/ee/user/project/deploy_tokens/) with `read_registry` scope in the source project.

### Option B: Use Default Retina CI/CD (Recommended for Development)

Default behavior when `SKIP_RETINA_CI` is not set. Builds and publishes to your fork's GitLab registries (no configuration required).

**Initial Setup:**

When forking via [GitLab UI](https://docs.gitlab.com/ee/user/project/repository/forking_workflow.html#create-a-fork), the pipeline in charge of building and pushing retina artifacts won't trigger automatically. This won't happen if you do a push using git commands.

To trigger the pipeline manually, please do a harmless modification in [retina/version.yml](../../retina/version.yml), like the comment line before the variables section. Optionally revert after pipeline completes.

**Ongoing Updates:**

Pipelines trigger automatically when you update main branch (via git push/merge or [GitLab's update fork button](https://docs.gitlab.com/ee/user/project/repository/forking_workflow.html#update-your-fork)), so Retina Images and Packages will be built after each update.

#### Use Custom Registries with Retina CI/CD

If you want to build Retina but publish to external/custom registries instead of GitLab's built-in ones.

**Container Registry Configuration:**

| Variable | Value | Example |
|----------|-------|---------|
| `RETINA_REGISTRY_URI` | Your custom container registry path | `myregistry.example.com/retina` |
| `DOCKER_AUTH_CONFIG` | Authentication for your registry | See Option A. You'll need write access to the registry. |

**Python Package Registry (PyPI) Configuration:**

| Variable | Value | Example |
|----------|-------|---------|
| `TWINE_USERNAME` | PyPI registry username | `gitlab-ci-token` or custom username |
| `TWINE_PASSWORD` | PyPI registry password/token | `$CI_JOB_TOKEN` or custom token |
| `TWINE_REPO` | PyPI registry URL | `https://gitlab.example.com/api/v4/projects/123/packages/pypi` |
