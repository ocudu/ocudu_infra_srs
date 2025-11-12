# OCUDU E2E Testing

This folder contains e2e tests sources, configurations and testbeds, alongside the Gitlab CI code to replicate SRS scheduled pipelines.

To run them, you need to install and configure [Retina framework](../retina/README.md)

## Gitlab Pipelines

### Manual Pipeline

We have a pipeline designed for triggered executions from the GitLab API or web interface. This pipeline orchestrates two main jobs:

1. **Build Job**: Compiles ocudu according to specified parameters
2. **E2E Job**: Runs selected end-to-end tests

When the E2E testbed is configured for Amarisoft and ZMQ, the pipeline will automatically attempt to build the ZMQ driver alongside the normal build process. This requires:

- The `AMARISOFT_PACKAGE_REGISTRY` variable to be available in the GitLab repository
- Proper access credentials to the registry as commented in the build [component documentation](../templates/README.md#download-urls-configuration).

Please refer to the [build and e2e component documentation](../templates/README.md) for more info.
