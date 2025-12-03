# Gitlab CI Components

- Build
- E2E Tests

## Build

This GitLab CI configuration file defines a reusable component for building the OCUDU software with customizable build parameters. It provides flexibility to:

- Configure different build flags and compilation options
- Use custom images
- Select OCUDU forks
- Support cache and custom infrastructure

This component can be included in GitLab CI pipelines:

```yml
include:
  - component: $CI_SERVER_FQDN/ocudu/ocudu-infra-srs/build@<VERSION>
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

## E2E Tests

Gitlab CI component to run a E2E Test for OCUDU using [Retina framework](../retina/README.md). It allows you to:

- Select existing tests to run using pytest options
- Select testbed where it will run
- Use compiled ocudu app from a previous job (f.e. created with the build component)

This component can be included in GitLab CI pipelines:

```yml
include:
  - component: $CI_SERVER_FQDN/ocudu/ocudu-infra-srs/build@<VERSION>
    inputs:
      job: build_ocudu
      ...
include:
  - component: $CI_SERVER_FQDN/ocudu/ocudu-infra-srs/e2e@<VERSION>
    inputs:
      build_job: build_ocudu
      job: e2e_test
      ...

stages: [build, e2e]
```

### FTP Server Configuration

Test artifacts are automatically saved to GitLab and optionally to an FTP server when configured. To configure an FTP server, please set following variables at Group/Project/Runner level:

- `FTP_SERVER_IP` - FTP server address
- `FTP_SERVER_PORT` - Connection port
- `FTP_SERVER_USER` - Authentication username
- `FTP_SERVER_PASS` - Authentication password
- `FTP_REMOTE_PATH` - Target directory path
