# Terraform Docker Image

This directory contains the Dockerfile for building a custom Terraform image used by all infrastructure automation pipelines.

## What's Included

The image is based on the official HashiCorp Terraform image and adds:
- **Python 3** - For running generation scripts
- **pip** - Python package manager
- **jq** - JSON processor for parsing Terraform output
- **PyYAML** - For parsing YAML cluster definitions
- **bash** - For complex shell scripts
- **requests** - Python library for HTTP requests

## Building the Image

The image is built automatically via CI/CD pipeline when changes are detected.

### Local Build

```bash
cd infrastructure/images/terraform
docker build --build-arg TERRAFORM_VERSION=1.12.1 -t terraform:1.12.1 .
```

### CI Build

The `.gitlab-ci.yml` in this directory handles:
- **Test build** on merge requests (doesn't push)
- **Build and publish** on main branch (pushes to registry)

## Usage

The image is referenced in `infrastructure/base/terraform.yml`:

```yaml
.terraform-base:
  image:
    name: ${GITLAB_REGISTRY_URI}/ci/infrastructure/terraform:${TERRAFORM_VERSION}
```

All Terraform jobs extend `.terraform-base` and automatically use this image.

## Updating Terraform Version

To update the Terraform version:

1. Update `TERRAFORM_VERSION` in `infrastructure/base/terraform.yml`
2. The CI will build the new version automatically
3. All pipelines will use the new version

## Registry

The image is pushed to:
```
${GITLAB_REGISTRY_URI}/ci/infrastructure/terraform:${TERRAFORM_VERSION}
```

For your organization, set `GITLAB_REGISTRY_URI` as a CI/CD variable pointing to your GitLab container registry.

## Dependencies

- **Base image**: `hashicorp/terraform:${TERRAFORM_VERSION}`
- **Alpine packages**: `python3`, `py3-pip`, `jq`, `py3-yaml`, `bash`
- **Python packages**: `requests`

## Customization

To customize the image for your organization:

1. Add required tools to the Dockerfile
2. Keep it minimal - only include what's needed for infrastructure automation
3. Test locally before pushing

Example: Adding kubectl:
```dockerfile
RUN apk add --no-cache kubectl
```

## Image Size

The image is relatively small (~200MB) because it's based on Alpine Linux.

## Security

- Uses official HashiCorp base image
- Only installs packages from Alpine repositories
- Python packages installed via pip with `--root-user-action=ignore` flag
