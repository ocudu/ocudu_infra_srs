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

The `download_urls_pre_build` input accepts a list of URLs to download at the beginning of the build job. It expects one URL per line.

Authentication header should be included in the variable itself. If using Gitlab Package Registry, the recommended approach would be to use a valid [deploy token](https://docs.gitlab.com/user/project/deploy_tokens) in the project where the package registry lives. For that, wget should include `--user="$DEPLOY_TOKEN_USER" --password="$DEPLOY_TOKEN_PASS"`

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
