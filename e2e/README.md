# E2E Testing

This folder contains E2E test sources, configurations and testbed definitions, alongside the GitLab CI code to replicate SRS scheduled pipelines.

## Test Definitions

Check [tests](tests/README.md) folder to know more about the E2E Testing approach, how tests are written and designed.

## GitLab Pipelines

### Prerequisites

**Amarisoft ZMQ Configuration**: When the E2E testbed is configured for Amarisoft and ZMQ, the pipeline will automatically attempt to build the ZMQ driver alongside the normal build process. This requires following variables:

| Variable | Description |
|----------|-------------|
| `AMARISOFT_PACKAGE_REGISTRY` | URL to the Amarisoft package repository |
| `AMARISOFT_PACKAGE_REG_USER` | Username for private package registry authentication (if applicable) |
| `AMARISOFT_PACKAGE_REG_PWD` | Password for private package registry authentication (if applicable) |

**Security best practices**:

- Variables must be **masked** to hide sensitive values in logs

For detailed configuration options, see the [build and E2E component documentation](../templates/README.md).

### Scheduled Pipelines

- functional

### Manual Pipeline

This pipeline is designed for on-demand executions triggered from the GitLab API or web interface. It orchestrates two main jobs:

1. **Build Job**: Compiles OCUDU according to specified parameters
2. **E2E Job**: Runs selected end-to-end tests

## Scripts

The [scripts directory](scripts/README.md) contains utilities to help you trigger customized pipelines in GitLab. See the [scripts documentation](scripts/README.md) for detailed usage instructions.
