# Cluster Setup

## Configure the cluster to use Retina

- Have `kubectl` access to your cluster

- Create a `retina` namespace.

- If the retina container registry is not public, you need to create a secret with the credentials:

```bash
kubectl -n retina create secret docker-registry registry-credentials \
  --docker-server='registry.gitlab.com' \
  --docker-username='username' \
  --docker-password='password'
```

For GitLab Container Registry, you can create a `Deploy Token` with `read_registry` scope.

- Generate a .kube/config file.

## Cluster Definition

The cluster definition is a YAML file that describes all resources available to Retina in your Kubernetes cluster. It serves as an inventory of your testing infrastructure. This includes both cluster-wide resources (like licenses and remote accessible PCs) and node-specific resources (like SDRs, RUs and compute capacity).

During test execution, Retina's orchestrator queries this information to:

- Determine which nodes can run specific test components
- Allocate hardware resources (SDRs, RUs, etc.) to tests
- Ensure tests only run on nodes with sufficient compute resources
- Manage shared resources like licenses.

Check the [Retina legend](./01_overview.md#legend) for terminology.

### File Structure

A cluster definition file contains three main sections:

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
```

#### Cluster Resources

Shared resources that can be used by any test in the cluster. Each resource type has specific required fields:

**License Resources** - Software licenses (e.g., Amarisoft):

```yaml
cluster_resource_list:
  - type: license
    model: amarisoft-ue-1       # License model/variant
    address: 10.11.22.333       # License server IP
    args: ueTag                 # License arguments
```

**Remote Resources** - Remote servers accessible via SSH (Amarisoft Callbox, Viavi emulator, GNB Server, etc.):

```yaml
  - type: remote
    model: gnbServer            # Remote system identifier
    address: 10.11.22.444       # Server IP address
    user: myUser                # SSH username
    password: myPassword        # SSH password
    path: "/urs/bin/..."        # Working directory path
```

**API Resources** - External API endpoints (Viavi API, Amarisoft Websocket, etc.):

```yaml
  - type: api
    model: myAPI                # API provider
    address: 10.11.22.555       # API server address
    port: 6666                  # API port
```

**Core Resources** - External core network endpoints:

```yaml
  - type: core
    model: myCore               # Core network provider
    address: 10.11.22.777       # Core network IP
    port: 38412                 # SCTP/NGAP port
    mask: 24                    # Network mask (prefix length)
```

**Important**: Each combination of `type` and `model` must be unique across all cluster resources.

#### Node Definitions

Each node entry describes compute resources and attached hardware:

```yaml
nodes:
  - name: sdr-node-01                    # Required: Kubernetes node name
    type: linux-x86                      # Node type/architecture
    compute-resources:                   # Required: Available compute capacity
      cpu: 12                            # CPU cores available for Retina
      memory: 22G                        # RAM available for Retina (using K8s notation)
      ephemeral-storage: 40G             # Temporary storage available for Retina
      hugepages-1Gi: 2Gi                 # Hugepages (optional)
    cpu_isolation:                       # Optional: CPU isolation for DPDK
      lcores_eal_args: "(0-1)@(1-7,9-15)"
    resources:                           # Optional: Attached hardware resources
      - type: sdr                        # Hardware type
        model: b200                      # Hardware model
        space: 2                         # Resource Space ID (an integer > 0)
```

**Important**: Items in the same resource space are reserved together. Put the same value to the resources that will be used together or can't be used at the same time. For example:

- Two SDRs that are wired between them must be in the same resource space.
- Multiple COTS phones and a SDR that are sharing the same space and bands must be in the same resource space.

**Node resource types:**

- **`sdr`**: Software Defined Radio (e.g., USRP B200, X300)
  - Required: `type`, `model`, `space`, `args`, `sample_rate`, `tx_gain`, `rx_gain`, `sync`
  - Optional: `connection`: `usb` or `network`.
  
- **`ru`**: Radio Unit
  - Required: `type`, `model`, `space`, `address`, `network_interface`, `ru_mac_address`, `du_mac_address`, `vlan_tag_up`, `vlan_tag_cp`, `prach_port_id`, `dl_port_id`, `ul_port_id`
  
- **`android`**: COTS UE devices
  - Required: `type`, `model`, `space`, `serial_id`, `imsi`, `k`, `amf`, `opc`, `adb_key`
  - Optional: `connection`: `usb`.
  
- **`accelerator`**: Hardware accelerators (e.g., FPGA, ACC100)
  - Required: `type`, `model`, `space`, `id`, `cb_mode`, `hwacc_type`, `pdsch_enc_nof_hwacc`, `pusch_dec_nof_hwacc`, `harq_context_size`, `args`
  - Optional: `connection`: `pci`.

### Deploying Your Cluster Definition

Once you've created your cluster definition file, deploy it to Kubernetes using the `retina-deploy-cluster` command.

#### Prerequisites

- Check [Configure the cluster to use Retina](#configure-the-cluster-to-use-retina) section.
- [Install retina or use a container](03_installation.mdx).

#### Deployment Command

```bash
# Deploy cluster definition
retina-deploy-cluster --input /path/to/your/cluster_definition.yaml

# Verify deployment
retina status --verbose
```

#### Dry Run

Test your configuration without applying changes:

```bash
retina-deploy-cluster --input /path/to/your/cluster_definition.yaml --dry-run
```
