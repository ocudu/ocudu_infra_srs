# Infrastructure Setup

This guide explains how to set up the infrastructure needed to run OCUDU end-to-end tests using the Retina framework.

## Requirements

To replicate this infrastructure you'll need:

- **Build OCUDU Resources**
  - Option A - GitLab Shared Runners: Use GitLab's cloud-based shared runners (no setup required)
  - Option B - Self-Hosted Runner: Set up a dedicated runner with:
    - Minimum recommended: 4+ CPU cores, 16GB+ RAM, 50GB+ disk space
    - Compatible runner tag configuration
- **Run OCUDU Resources**: Server or PC with sufficient resources to run the cu, du and gNB applications
- **Third-Party Software & Licenses**:
  - Amarisoft Licenses and servers: Required for UE and core network emulation
  - Viavi: For advanced performance and stress testing
- **Hardware Under Test**: Depending on your test scenarios, you may need:
  - SDRs (Software Defined Radios): For RF testing (e.g., USRP)
  - O-RUs (Open Radio Units): For O-RAN fronthaul testing
  - COTS UEs (Commercial Off-The-Shelf User Equipment): Commercial phones for real-world testing
- **Kubernetes Cluster**: For orchestrating test infrastructure
  - Version: 1.24+ recommended
  - All test servers must be either:
    - Part of the Kubernetes cluster (as nodes), OR
    - Reachable from the cluster via network connectivity
- **GitLab Runner for E2E Jobs**: Dedicated runner to execute Retina-based tests
  - Can be installed:
    - Option A - Inside the cluster: As a Kubernetes pod/deployment (recommended)
    - Option B - Outside the cluster: On a separate machine with network access to the cluster
  - Must have `kubectl` access to the Kubernetes cluster

## Setup Steps

Follow these steps to set up your testing infrastructure:

### 1. Fork the Repository

Check [the forking guide](./_docs/01_fork.md).

### 2. Configure Your Servers

Prepare the physical or virtual servers that will be used for testing so they can run OCUDU and other tools with good performance.

#### Using IaC

OCUDU Infra SRS project provides Terraform and CI files to help you to configure your servers by setting up:

- [LinuxPTP](./k8s/Helm/linuxptp/main.tf)
- [TuneD](./k8s/Helm/tuned/main.tf)

### 3. Set Up a Kubernetes Cluster

Deploy a Kubernetes cluster for test orchestration.

### 4. Install Retina in the Cluster

#### Manual Retina Setup

Deploy the Retina framework components to your Kubernetes cluster by following [the instructions in the retina documentation](../retina/_docs/02_cluster_setup.md#configure-the-cluster-to-use-retina).

#### IaC Retina Setup

[Terraform + GitLab CI IaC Solution](./retina-cluster-setup/README.md).

#### Retina Auxiliary Cronjobs

To make the experience with Retina inside your cluster better, we provide some cronjobs:

- Amarisoft License Synchronization: Queries an Amarisoft License Server to found Licenses usage outside of Retina and reserves the resource in Retina. This way, Retina status will always reflect the real usage status even if the license is being used somewhere else.
- Runner Manager: In case a node is shared between a Gitlab Runner and Retina, this job will take care of pausing / resuming the runners when a Retina test is using that server.

[Check here for more info](./retina-cronjobs/tf/main.tf).

### 5. Save the Cluster Definition in Retina

[Follow the instructions about Cluster Definition in the retina documentation](../retina/_docs/02_cluster_setup.md#cluster-definition).

### 6. Set Up a Build and a Retina Runner

#### Manual Gitlab Runners Setup

Check the [Manual Gitlab Runners Setup guide](./_docs/02_runners.md).

#### IaC Gitlab Runners Deploy

[Read the instructions here](./gitlab-runner/README.md)

### 7. Test Your Setup

Verify your infrastructure is ready by triggering a test pipeline (see [e2e scripts documentation](../e2e/scripts/README.md) for details)
