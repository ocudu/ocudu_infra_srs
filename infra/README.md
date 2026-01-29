# Infrastructure Setup

This guide explains how to set up the infrastructure needed to run OCUDU end-to-end tests using the Retina framework.

## Requirements

To replicate this infrastructure you'll need:

### Build OCUDU Resources

Choose one of the following options:

- **Option A - GitLab Shared Runners**: Use GitLab's cloud-based shared runners (no setup required)
- **Option B - Self-Hosted Runner**: Set up a dedicated runner with:
  - Minimum recommended: 4+ CPU cores, 16GB+ RAM, 50GB+ disk space
  - Compatible runner tag configuration

### Run OCUDU Resources

- Server or PC with sufficient resources to run the cu, du and gNB applications

### Third-Party Software & Licenses

- **Amarisoft Licenses and servers**: Required for UE and core network emulation
- **Viavi**: For advanced performance and stress testing

### Hardware Under Test

Depending on your test scenarios, you may need:

- **SDRs (Software Defined Radios)**: For RF testing (e.g., USRP)
- **O-RUs (Open Radio Units)**: For O-RAN fronthaul testing
- **COTS UEs (Commercial Off-The-Shelf User Equipment)**: Commercial phones for real-world testing

### Kubernetes Infrastructure

- **Kubernetes Cluster**: For orchestrating test infrastructure
  - Version: 1.24+ recommended
  - All test servers must be either:
    - Part of the Kubernetes cluster (as nodes), OR
    - Reachable from the cluster via network connectivity
  
### Retina Runner

- **GitLab Runner for E2E Jobs**: Dedicated runner to execute Retina-based tests
  - Can be installed:
    - **Inside the cluster**: As a Kubernetes pod/deployment (recommended)
    - **Outside the cluster**: On a separate machine with network access to the cluster
  - Must have `kubectl` access to the Kubernetes cluster

## Setup Steps

Follow these steps to set up your testing infrastructure:

### 1. Fork the Repository

Create your own copy of this repository to customize it for your infrastructure:

```bash
# Clone your forked repository
git clone https://gitlab.com/your_user_or_group/ocudu_infra_srs.git
cd ocudu_infra_srs
```

### 2. Configure Your Servers

Prepare the physical or virtual servers that will be used for testing.

### 3. Set Up a Kubernetes Cluster

Deploy a Kubernetes cluster for test orchestration.

### 4. Install Retina in the Cluster

Deploy the Retina framework components to your Kubernetes cluster.

### 5. Configure Cluster Information in Retina

Update Retina configuration files with your cluster-specific details.

### 6. Set Up a Build Runner

Configure a GitLab runner for building OCUDU:

**Option A - Use GitLab Shared Runners:**

- No setup required
- Enable shared runners in your GitLab project settings

**Option B - Self-hosted Runner:**

Go to [GitLab Documentation](https://docs.gitlab.com/runner/install/) for more details.

### 7. Set Up an E2E Runner

Configure a GitLab runner with access to your Kubernetes cluster for running tests.

### 8. Test Your Setup

Verify your infrastructure is ready by triggering a test pipeline (see [e2e scripts documentation](../e2e/scripts/README.md) for details)
