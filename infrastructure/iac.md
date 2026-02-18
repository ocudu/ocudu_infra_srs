# Infrastructure Automation

This directory contains reusable CI/CD templates and configuration scripts for deploying and managing Retina test lab infrastructure.

## Overview

The infrastructure automation provides **generic, reusable CI/CD templates** for:

- **GitLab Runner deployment** - Automated deployment of GitLab runners for build, IAC, and E2E tests
- **Kubernetes core resources** - Coredump cleanup DaemonSet and etcd defragmentation CronJobs
- **RBAC configuration** - Kubernetes role-based access control setup
- **Helm services** - Tuned and LinuxPTP service deployments
- **Retina runner management** - Automated runner scheduling and cleanup cronjobs
- **Configuration generation** - Python-based Jinja2 templating for cluster-specific configs

**Key Design Principles:**

- **100% Generic**: No hardcoded cluster names, IDs, or organization-specific values
- **Public/Private Split**: Templates in public repo, secrets/configs in your private repo
- **Parameterized**: All cluster-specific values passed as CI/CD variables
- **Replicable**: Any organization can use these templates with their own infrastructure

## Architecture

```text
infrastructure/
├── base/                            # Reusable CI/CD base definitions
│   └── terraform.yml                # Terraform job template with GitLab state backend
├── images/
│   └── terraform/                   # Custom Terraform Docker image
│       ├── Dockerfile               # Terraform + Python + tools
│       └── .gitlab-ci.yml           # CI to build and publish image
├── generator/                       # Configuration generation tooling
│   ├── generate.py                  # Main generation script
│   ├── templates/                   # Jinja2 templates for Terraform and Helm
│   └── scripts/                     # Utility scripts (detect_changes.sh, etc.)
├── gitlab-runner/                   # GitLab runner deployment
│   ├── .gitlab-ci.yml               # Generic runner deployment pipeline
│   └── ...
├── k8s/
│   ├── core/                        # Core k8s resources (coredump, etcd-defrag)
│   │   ├── coredump/                # Coredump DaemonSet manifest template
│   │   ├── etcd-defrag/             # etcd-defrag CronJob manifest template
│   │   ├── tf/                      # Terraform configurations
│   │   │   ├── coredump/            # Coredump Terraform module
│   │   │   └── etcd-defrag/         # etcd-defrag Terraform module
│   │   ├── .gitlab-ci-coredump.yml  # Generic coredump child pipeline
│   │   └── .gitlab-ci-etcd-defrag.yml # Generic etcd-defrag child pipeline
│   ├── rbac/                        # RBAC configuration
│   └── Helm/
│       ├── tuned/                   # Tuned Helm service
│       └── linuxptp/                # LinuxPTP Helm service
├── retina-cronjobs/                   # Retina cronjobs and management
│   ├── image/                       # Docker image with Python scripts
│   ├── manifests/                   # Kubernetes manifests for cronjobs
│   ├── tf/                          # Terraform for retina-cronjobs deployment
│   ├── registry-credentials/        # Helm chart for registry credentials
│   └── tf-registry-credentials/     # Terraform for registry credentials deployment
├── rbac/                            # RBAC manifest templates
└── scripts/                         # Helper scripts (runner_balancer.py, etc.)
```

## Usage

### 1. Fork ocudu_infra_srs (Public Repo)

This repository is public and contains all the reusable CI/CD templates and configuration generation logic.

```bash
git clone https://gitlab.com/ocudu/ocudu.git
```

### 2. Create Your Private Infrastructure Repository

Create a private repository for your organization that will contain:

- **Cluster definitions** (YAML files describing your infrastructure)
- **Secrets** (tokens, credentials, kubeconfigs)
- **.gitlab-ci.yml** that includes templates from `ocudu_infra_srs`

Directory structure for your private repo:

```text
your-private-infra-repo/
├── .gitlab-ci.yml                      # Triggers CI from ocudu_infra_srs
├── cluster_definition/
│   ├── your_cluster.yaml              # Your cluster definition
│   ├── your_cluster_runners.yaml      # Runner configuration
│   └── your_cluster_services.yaml     # Services configuration
├── secrets/
│   └── gitlab-tokens-your-org.yaml    # GitLab tokens (gitignored!)
└── gitlab-runner/                      # Generated files (artifacts)
    └── your-cluster/
        ├── tf/                         # Generated Terraform
        └── manifests/                  # Generated manifests
```

### 3. Create Cluster Definition Files

Cluster definitions are YAML files that describe your infrastructure. A complete cluster definition consists of **three YAML files** per cluster:

```text
cluster_definition/
├── my_cluster.yaml              # Nodes, resources, global settings (Retina + infra)
├── my_cluster_runners.yaml      # GitLab runner configs (references nodes by name)
└── my_cluster_services.yaml     # Service configs: tuned, linuxptp (references nodes by name)
```

The runners and services files reference node names defined in the main cluster definition file. All three files must use consistent node names.

The **main cluster definition file** (`my_cluster.yaml`) contains three sections:

1. **`global`**: Cluster-wide settings and metadata
2. **`cluster_resource_list`**: Shared resources accessible across the cluster
3. **`nodes`**: Individual node definitions with their compute and hardware resources

#### Global Section

```yaml
global:
  name: my-cluster              # Required: Cluster name
  networking-mode: nodePort     # Required: Kubernetes networking mode (nodePort, loadBalancer, etc.)
  version: 1.0.0                # Required: file version
  dnsPolicy: Default            # Optional: DNS policy (Default, ClusterFirst, ClusterFirstWithHostNet, None)

  # GitLab runner configuration (used by infrastructure automation)
  gitlab_runner:
    image:
      registry: registry.gitlab.com
      image: gitlab-org/gitlab-runner
      tag: ubuntu-v18.2.0
    gitlab_url: https://gitlab.com/
    check_interval: 1           # Runner polling interval in seconds
    cache:                      # S3 cache for runner build artifacts
      type: s3
      path: gl-runner-amd64
      s3:
        server_address: "10.0.0.1:9000"
        access_key: "minio-admin"
        secret_key: "secret"
        bucket_name: "gl-runner-cache"
        insecure: true
    host_aliases:               # Optional: DNS aliases for the runner pods
      ip: "10.0.0.99"
      hostnames:
        - "lb-apiserver.kubernetes.local"

  # Helm chart and container image versions (used by service deployments)
  linuxptp_version: "1.3.0"              # LinuxPTP Helm chart version
  tuned_version: "v2.21.0_1.0.0"                 # Tuned Helm chart version
  linuxptp_image_tag: "v4.4_1.1.2"       # LinuxPTP container image tag
  tuned_image_tag: "v2.21.0_1.0.0"               # Tuned container image tag (amd64)
  tuned_image_tag_arm64: "v2.21.0_1.0.0"   # Tuned container image tag (arm64)
```

The `gitlab_runner` block configures the GitLab runner image and caching for all runners deployed on this cluster. The `host_aliases` field allows runner pods to resolve custom DNS names (e.g., the Kubernetes API server load balancer).

The Helm chart and image version fields control which versions of tuned and linuxptp are deployed to the cluster nodes.

#### Node Resources

Node resource types include:

- **`sdr`**: Software Defined Radio (e.g., USRP B200, X300)
  - Required: `type`, `model`, `space`, `args`, `sample_rate`, `tx_gain`, `rx_gain`, `sync`
  - Optional: `connection`: `usb` or `network`.
  - Example:
    ```yaml
    - type: sdr
      model: b200
      space: 1
      args: "type=b200,num_recv_frames=64,num_send_frames=64"
      sample_rate: 23040000
      tx_gain: 50
      rx_gain: 40
      sync: internal
    ```

- **`zmq`**: Virtual resource for ZMQ-based simulation (no physical hardware required)
  - Required: `type`, `model`, `space`
  - The `model` is typically `slot`. Multiple ZMQ slots can be defined per node for parallel test scenarios.
  - Example:
    ```yaml
    - type: zmq
      model: slot
      space: 1
    - type: zmq
      model: slot
      space: 2
    ```

For the full list of node resource types (ru, android, accelerator, etc.), see the [Retina Cluster Setup docs](../retina/_docs/02_cluster_setup.md#node-definitions).

#### Cluster Types

Cluster types are logical labels used in [runner definitions](#runner-definitions) to control which GitLab group or organization a runner serves. Each runner specifies one or more `cluster_types` it belongs to.

This enables multi-organization runner filtering on a shared cluster. For example, a node can host runners for both `srs-dc` and `ocudu-dc`, each registered to a different GitLab group.

Common naming convention: `<org>-<location>`, e.g.:
- `srs-bcn` — SRS organization, Barcelona lab
- `srs-dc` — SRS organization, data center
- `ocudu-dc` — OCUDU organization, data center
- `srs-bcn-office` — SRS organization, Barcelona office

#### Complete Example

A minimal but realistic cluster definition:

```yaml
global:
  name: my-cluster
  networking-mode: nodePort
  version: 1.0.0
  dnsPolicy: Default
  gitlab_runner:
    image:
      registry: registry.gitlab.com
      image: gitlab-org/gitlab-runner
      tag: ubuntu-v18.2.0
    gitlab_url: https://gitlab.com/
    check_interval: 1
    cache:
      type: s3
      path: gl-runner-amd64
      s3:
        server_address: "10.0.0.1:9000"
        access_key: "minio-admin"
        secret_key: "secret"
        bucket_name: "gl-runner-cache"
        insecure: true
  linuxptp_version: "1.3.0"
  tuned_version: "v2.21.0_1.0.0"
  linuxptp_image_tag: "v4.4_1.1.2"
  tuned_image_tag: "v2.21.0_1.0.0"

cluster_resource_list:
  - type: license
    model: amarisoft-mme-nr
    address: 10.0.0.50
    args: mme

nodes:
  - name: worker-01
    type: linux-x86
    compute-resources:
      cpu: 10
      memory: 58G
      ephemeral-storage: 200G
    resources:
      - type: zmq
        model: slot
        space: 1
      - type: zmq
        model: slot
        space: 2

  - name: build-server
    type: linux-x86
    compute-resources:
      cpu: 32
      memory: 64G
      ephemeral-storage: 500G
    resources: []
```

#### Runner Definitions

The runner definition file (`my_cluster_runners.yaml`) configures GitLab runners deployed on each node. Runners are organized by node name, matching the `name` field in the main cluster definition.

##### Structure

```yaml
runners:
  <node-name>:               # Must match a node name from the cluster definition
    - id: 12345678            # GitLab runner ID
      name: glr-my-runner     # Runner name (displayed in GitLab)
      token: glrt-xxxxx       # Runner authentication token
      cluster_types:          # Cluster type labels for filtering
        - my-cluster-type
      concurrent: 4           # Max concurrent jobs
      tags: amd64, build      # Comma-separated runner tags
      cpu_request: 4          # CPU request (Kubernetes)
      cpu_limit: 4            # CPU limit (Kubernetes)
      memory_request: 8Gi     # Memory request
      memory_limit: 8Gi       # Memory limit
      node_tolerations:       # Node toleration for scheduling
        machine=<node-name>: NoSchedule
      # ... more runners for this node
  <another-node>:
    - ...
```

##### Required Fields

| Field | Description |
|-------|-------------|
| `id` | GitLab runner ID (from runner registration) |
| `name` | Display name, convention: `glr-<cluster-type>-<node>` |
| `token` | Runner authentication token (`glrt-` prefix) |
| `cluster_types` | List of [cluster type](#cluster-types) labels |
| `concurrent` | Maximum number of concurrent jobs |
| `tags` | Comma-separated list of runner tags |
| `cpu_request` / `cpu_limit` | Kubernetes CPU resources |
| `memory_request` / `memory_limit` | Kubernetes memory resources |
| `node_tolerations` | Kubernetes toleration to schedule on the target node |

##### Optional Fields

| Field | Description |
|-------|-------------|
| `image` | Override the runner image (defaults to `global.gitlab_runner.image`) |
| `check_interval` | Override polling interval |
| `arch` | Architecture override (e.g., `arm64`) |
| `disable_when` | List of schedule types to pause the runner (e.g., `nightly`, `weekly`) |
| `priority_class_name` | Kubernetes PriorityClass (e.g., `gitlab-glr-priority`) |
| `service_account` | Custom Kubernetes service account |
| `rbac` | RBAC rules for cluster-wide access (used by E2E test runners) |
| `ephemeral_storage_request` / `ephemeral_storage_limit` | Ephemeral storage resources |
| `ephemeral_storage_request_overwrite_max_allowed` | Max ephemeral storage a job can request |
| `helper_cpu_limit` / `helper_memory_limit` | Resources for the GitLab runner helper pod |

##### Example

```yaml
# my_cluster_runners.yaml
runners:
  worker-01:
    - id: 49278383
      name: glr-my-org-worker-01
      cluster_types:
        - my-org-cluster
      token: glrt-xxxxx
      concurrent: 2
      tags: amd64, on-prem-amd64, sctp
      cpu_request: 5
      cpu_limit: 5
      memory_request: 12Gi
      memory_limit: 12Gi
      node_tolerations:
        machine=worker-01: NoSchedule
  build-server:
    - id: 49638831
      name: glr-my-org-build-server
      cluster_types:
        - my-org-cluster
      token: glrt-yyyyy
      concurrent: 8
      tags: amd64, build
      cpu_request: 6
      cpu_limit: 6
      memory_request: 12Gi
      memory_limit: 12Gi
      node_tolerations:
        machine=build-server: NoSchedule
```

**Note**: A single node can host multiple runners targeting different `cluster_types`. This is how multi-organization support works on shared infrastructure.

#### Service Definitions

The service definition file (`my_cluster_services.yaml`) configures **tuned** (kernel tuning) and **linuxptp** (PTP time synchronization) for each node.

##### Structure

The file has two top-level sections:

- **`global`**: Shared configuration defaults for all services
- **`services`**: Per-node configuration, keyed by node name

```yaml
global:
  tuned:
    image:
      repository: registry.gitlab.com/ocudu/ocudu_elements/ocudu_helm/tuned-agent
      pullPolicy: IfNotPresent
    hostPathTuned: /usr/lib/tuned
    securityContext:
      privileged: true
    restartOnConfigChange: true
    reboot:
      enabled: true
      cmd: /sbin/shutdown -r +1 'tuned profile applied by helm'
      markerDir: /var/lib/tuned-helm
  linuxptp:
    config:
      domainNumber: 24
      network_transport: L2
      delay_mechanism: E2E
      time_stamping: hardware
      # ... additional PTP parameters

services:
  <node-name>:
    tuned:
      enabled: true/false
      profileContent: |-
        # Tuned profile content (INI format)
        [main]
        summary=My tuned profile
        [bootloader]
        cmdline="..."
        [cpu]
        governor=performance
        # ...
      startupScriptContent: |-
        #!/bin/bash
        # Startup script for hardware initialization
        # SR-IOV, DPDK, ethtool tuning, etc.
    linuxptp:
      enabled: true/false
      interface_name: enp1s0f0   # NIC for PTP synchronization
      config:                     # Optional: per-node overrides
        summary_interval: -3
```

##### Tuned Service

The tuned service applies kernel and hardware tuning to nodes. Each node's configuration consists of:

- **`profileContent`**: A tuned profile in INI format with sections like `[bootloader]` (kernel parameters), `[cpu]` (governor settings), `[sysctl]` (kernel tunables), `[vm]` (hugepages), and `[sysfs]` (direct sysfs writes).
- **`startupScriptContent`**: A shell script executed on node startup. Typically configures SR-IOV virtual functions, DPDK device binding, NIC ring buffers, and traffic control settings.
- **`image_tag`**: Optional override for the tuned image tag (e.g., `v2.21.0_1.0.0-arm64` for ARM64 nodes).

##### LinuxPTP Service

The linuxptp service provides PTP time synchronization. Global PTP parameters are defined once in `global.linuxptp.config` and apply to all nodes. Per-node settings only need:

- **`enabled`**: Whether PTP is active on this node
- **`interface_name`**: The NIC used for PTP (must support hardware timestamping)
- **`config`**: Optional per-node overrides for specific PTP parameters

#### Secrets Files

Runner management cronjobs require a GitLab API token stored in a secrets file:

```text
cluster_definition/secrets/gitlab-tokens-<org-name>.yaml
```

The file contains a single field:

```yaml
# GitLab API token for managing runners
# Scope: api
# Group: your-group (group-id)
# Cluster: your-cluster
gitlab_runner_token: glpat-xxxxx
```

The file name is derived from the organization/cluster name (e.g., `gitlab-tokens-srs-bcn-office.yaml`). These files **must be gitignored** as they contain sensitive credentials.

#### Adding a New Cluster

Step-by-step checklist for adding a new cluster to the infrastructure:

1. **Create the main cluster definition**
   - Create `cluster_definition/<name>.yaml` with `global`, `cluster_resource_list`, and `nodes` sections
   - Set `global.name` to your cluster identifier
   - Define all nodes with their compute resources and attached hardware

2. **Create the runner definition**
   - Create `cluster_definition/<name>_runners.yaml`
   - Define runners for each node, referencing node names from step 1
   - Choose a [cluster type](#cluster-types) label (e.g., `my-org-my-cluster`)
   - Register runners in GitLab and fill in `id` and `token` fields

3. **Create the service definition**
   - Create `cluster_definition/<name>_services.yaml`
   - Configure tuned profiles and linuxptp for each node
   - Set appropriate kernel parameters, CPU governors, and NIC tuning per node role

4. **Create the secrets file**
   - Create `cluster_definition/secrets/gitlab-tokens-<org>.yaml` with a GitLab API token
   - Ensure the file is gitignored

5. **Deploy the cluster definition to Kubernetes**
   ```bash
   retina-deploy-cluster --input cluster_definition/<name>.yaml
   retina status --verbose
   ```

6. **Add CI/CD jobs** (see [Configure Your .gitlab-ci.yml](#5-configure-your-gitlab-ciyml))
   - Add runner deployment, service deployment, and core resource jobs to `.gitlab-ci.yml`
   - Create required CI/CD variables (`KUBECONFIG`, runner tokens, etc.)

7. **Validate**
   - Verify YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('cluster_definition/<name>.yaml'))"`
   - Run a dry-run deployment
   - Trigger a CI pipeline and verify all jobs succeed

### 4. Set Up GitLab CI/CD Variables

In your private repository's CI/CD settings (Settings → CI/CD → Variables), add:

| Variable | Description | Protected | Masked | Used By |
|----------|-------------|-----------|--------|---------|
| `YOUR_KUBECONFIG_VAR` | Kubeconfig for cluster access | ✅ | ❌ | All deployments |
| `YOUR_RUNNER_TOKEN` | GitLab runner registration/update token | ✅ | ✅ | GitLab runner deployment |
| `CODEBOT_USERNAME` | GitLab username for Terraform state backend | ✅ | ❌ | All Terraform jobs |
| `CODEBOT_TOKEN` | GitLab token for Terraform state backend | ✅ | ✅ | All Terraform jobs |
| `REGISTRY_AUTH` | Base64-encoded Docker config JSON for registry authentication | ❌ | ✅ | Registry credentials deployment |
| `GITLAB_REGISTRY_URI` | GitLab container registry URI (e.g., `registry.gitlab.com/your-org`) | ❌ | ❌ | Image builds |

**Note on `REGISTRY_AUTH`**: This variable must contain a base64-encoded Docker config JSON in the format:

```json
{"auths":{"registry.gitlab.com":{"username":"...","password":"...","auth":"..."}}}
```

The variable must **not** be protected so it's available on feature branches during testing.

### 5. Configure Your .gitlab-ci.yml

Use the provided `gitlab-ci.yml.examples` as a starting point. Copy it to your private repo and customize:

```yaml
# .gitlab-ci.yml in your private repo
include:
  - project: ocudu/ocudu
    file: .gitlab/ci-shared/workflow.yml
    ref: dev
  - project: ocudu/ocudu
    file: .gitlab/ci-shared/docker.yml
    ref: dev

stages:
  - child
  - deployer

# Deploy GitLab runners
deploy-gitlab-runners:
  stage: child
  variables:
    CLUSTER_DEF: cluster_definition/your_cluster.yaml
    CLUSTER_TYPE: your-cluster-type
    OUTPUT_DIR: gitlab-runner/your-cluster
    TF_STATE_NAME: helm-your-cluster
    RUNNER_UPDATE_TOKEN_VAR: $YOUR_RUNNER_TOKEN
    RUNNERS_DEF: cluster_definition/your_cluster_runners.yaml
  trigger:
    include:
      - project: ocudu/ocudu
        ref: dev
        file: infrastructure/gitlab-runner/.gitlab-ci.yml
    strategy: depend
```

### 6. Push and Run

Commit your changes and push to GitLab. The CI pipeline will:

1. Clone `ocudu_infra_srs` for templates and scripts
2. Generate cluster-specific Terraform and manifests
3. Validate and plan Terraform changes
4. Apply changes to your cluster (on merge to default branch)

## Key Features

### Artifact-Based Workflow

Generated files are created as CI artifacts and are NOT committed to the repository:

- Terraform files: `*.tf`
- Kubernetes manifests: `*.yaml`

This keeps your repository clean and prevents merge conflicts.

### Multi-Cluster Support

The same CI templates support multiple clusters by passing different variables:

```yaml
parallel:
  matrix:
    - CLUSTER_TYPE: cluster-1
      CLUSTER_DEF: cluster_definition/cluster1.yaml
    - CLUSTER_TYPE: cluster-2
      CLUSTER_DEF: cluster_definition/cluster2.yaml
```

### Secrets Management

All secrets remain in your private repository:

- Kubeconfigs: Stored as CI/CD variables
- GitLab tokens: Stored as CI/CD variables or in `secrets/` (gitignored)
- Registry credentials: Deployed via Helm secrets

### Terraform State

Terraform state is stored in GitLab's HTTP backend:

- Project-specific: State is stored in the running project (your private repo)
- State name: Derived from `TF_STATE_NAME` variable
- Locking: Automatic via GitLab API

## Configuration Generation

The `generate.py` script uses Jinja2 templates to create cluster-specific configurations:

```bash
python3 infrastructure/generator/generate.py \
  cluster_definition/your_cluster.yaml \
  your-cluster-type \
  output-directory \
  --service-def cluster_definition/your_cluster_services.yaml \
  --service-name tuned
```

Templates are located in `infrastructure/generator/templates/`:

- `runner.tf.j2` - GitLab runner Terraform
- `helm_chart.tf.j2` - Helm chart deployments
- `cronjob.yaml.j2` - Kubernetes cronjob manifests

## Testing

### CI Testing

Test CI pipelines on merge requests:

1. Create a branch with changes to cluster definitions
2. Open a merge request
3. CI runs validation and plan stages
4. Review Terraform plan output
5. Manually trigger apply if needed

## Troubleshooting

### Pipeline Fails with "File not found"

Ensure your cluster definition files exist in the private repo:

```bash
cluster_definition/your_cluster.yaml
cluster_definition/your_cluster_runners.yaml
```

### Runner Registration Fails

Check that:

1. `RUNNER_UPDATE_TOKEN_VAR` is set correctly
2. Token has permissions to register runners
3. Cluster can reach gitlab.com

### Generated Files Not Found

Verify:

1. Generate job succeeded
2. Artifacts were created
3. Dependent jobs have `needs: [generate]`

## Contributing

To contribute improvements to the infrastructure automation:

1. Fork `ocudu_infra_srs`
2. Create a feature branch
3. Test changes in your private infrastructure repo
4. Submit a merge request to `ocudu_infra_srs`

## License

This project is part of the OCUDU Infrastructure SRS repository.

## Support

For issues or questions:

- Open an issue in the `ocudu_infra_srs` project
- Contact the infrastructure team
