# Gitlab CI Components

- Build

## Build

This GitLab CI configuration file defines a reusable component for building the OCUDU software with customizable build parameters. It provides flexibility to:

- Configure different build flags and compilation options
- Use custom images
- Select OCUDU forks
- Support cache and custom infrastructure

This component can be included in GitLab CI pipelines:

```yml
include:
  - component: $CI_SERVER_FQDN/softwareradiosystems/ocudu-infra-srs/build@<VERSION>
    inputs:
      ...

stages: [build]
```

### Download URLs Configuration

The `download_urls_pre_build` input accepts a list of URLs to download at the beginning of the build job. Authentication is handled via [job token](https://docs.gitlab.com/ci/jobs/ci_job_token/):

- URLs must be accessible using the CI job token
- Refer to the [job token documentation](https://docs.gitlab.com/ci/jobs/ci_job_token/) for:
  - Default access scope and limitations
  - Granting access to external repositories
  - Configuring access to other GitLab resources
