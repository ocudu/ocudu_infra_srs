# Retina Request File

The Retina request file defines the testbed configuration for your test. It's a core input for tests (via `retina-launcher`) and the Retina orchestrator, specifying what resources to deploy in the Kubernetes cluster.

## Overview

A Retina request file is a YAML document describing an array of pods (containers) to deploy. Here's a complete example:

```yml
- name: ocudu-gnb
  type: gnb
  image: ${RETINA_REGISTRY_URI}/ocudu-gnb:${RETINA_VERSION}
  requirements:
    cpu:
      requests: 6
      limits: 6
    memory:
      requests: "26G"
      limits: "26G"
    ephemeral-storage:
      requests: "15G"
      limits: "15G"
  resources:
    - type: zmq
  environment:
    - PATH: ${CONTAINER_PATH}:${OCUDU_PATH}/build_retina/apps/gnb
    - LD_LIBRARY_PATH: /opt/rohc/lib/
  shared_files:
    - local_path: ${OCUDU_PATH}/build_retina/apps/gnb/gnb
      remote_path: /usr/local/bin/gnb
      is_executable: true

- name: open5gs
  type: 5gc
  image: ${RETINA_REGISTRY_URI}/open5gs:${OPEN5GS_VERSION}_${RETINA_VERSION}
  requirements:
    cpu:
      requests: 1
    memory:
      requests: "4G"
    ephemeral-storage:
      requests: "3G"
      limits: "3G"
```

## Configuration Reference

Each pod in the array supports the following fields:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | ✓ | string | Unique identifier for the pod in the cluster |
| `image` | ✓ | string | Container image URI (e.g., from `registry.gitlab.com` or `hub.docker.com`) |
| `type` | ✓ | enum | Pod type: `ue`, `gnb`, `cu`, `du`, `5gc`, `ric`, `channel-emulator`, `generic` |
| `labels` | | array | Custom Kubernetes labels (see [Custom Labels](#custom-labels)) |
| `requirements` | ✓ | object | Resource requirements (see [Requirements](#requirements)) |
| `resources` | | array | Hardware resources to book (see [Resources](#resources)) |
| `environment` | | array | Environment variables for the container |
| `shared_files` | | array | Files to copy into the container (see [Shared Files](#shared-files)) |

### Requirements

Compute requirements define CPU, memory, and storage needs for each pod. All requirements are optional, so the user can require any compute resource and requests and/or limits.

#### Structure

```yml
requirements:
  cpu:
    requests: 6
    limits: 6
  memory:
    requests: "26G"
    limits: "26G"
  ephemeral-storage:
    requests: "15G"
    limits: "15G"
  hugepages-1Gi:
    requests: "2Gi"
```

#### Requests vs Limits

- **`requests`**: Resources **reserved exclusively** for the pod. Guaranteed to be available.
- **`limits`**: Maximum resources the pod can use. The pod can consume beyond requests up to this limit if available on the node.

If limits are not specified, the pod can use all available resources on the node beyond its requests.

[Learn more in Kubernetes documentation](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#requests-and-limits)

#### CPU

CPU resources are measured in CPU units:

- **1 CPU unit** = 1 physical core OR 1 virtual core
- **Fractional values allowed**: `0.5` = half a CPU core
- **Millicpu notation**: `100m` = `0.1` CPU = one hundred millicpu

Examples: `1`, `0.5`, `500m`, `2000m`

CPU is always an absolute amount, regardless of the node's total capacity.

#### Memory

Memory is measured in bytes with the following suffixes:

| Suffix | Type | Example | Equivalent |
|--------|------|---------|------------|
| `E, P, T, G, M, k` | Decimal | `400M` | 400 megabytes |
| `Ei, Pi, Ti, Gi, Mi, Ki` | Binary | `400Mi` | 400 mebibytes |

**Common mistake**: `400m` = 0.4 bytes (not megabytes). Use `400M` or `400Mi` instead.

#### Ephemeral Storage

Ephemeral storage uses the same byte notation as memory:

| Suffix | Example | Meaning |
|--------|---------|---------|
| `G` | `15G` | 15 gigabytes |
| `Gi` | `15Gi` | 15 gibibytes |
| `M` | `500M` | 500 megabytes |
| `Mi` | `500Mi` | 500 mebibytes |

#### Hugepages

Hugepages provide large memory pages for applications requiring high-performance memory access. Kubernetes supports hugepages as a schedulable resource.

**Supported page sizes:**

- `hugepages-2Mi`: 2 MiB hugepages
- `hugepages-1Gi`: 1 GiB hugepages

**Example configuration:**

```yml
requirements:
  hugepages-1Gi:
    requests: "2Gi"    # Requests 2 x 1GiB hugepages
    limits: "2Gi"      # Optional: Maximum hugepages allowed
  hugepages-2Mi:
    requests: "512Mi"  # Requests 256 x 2MiB hugepages
```

**Important notes:**

- Hugepages must be pre-allocated on the Kubernetes node
- The node must have hugepages enabled in the kernel
- Hugepages requests should equal limits (if both are specified)
- Use binary suffixes (`Gi`, `Mi`) matching the page size

[Learn more about hugepages in Kubernetes](https://kubernetes.io/docs/tasks/manage-hugepages/scheduling-hugepages/)

### Resources

Hardware resources to allocate to the pod:

```yml
resources:
  - type: zmq           # Required: Resource type
    model: b200         # Optional: Specific model/variant
```

Common resource types: `zmq`, `sdr`, `ru`, etc.

### Shared Files

Files to copy from the local system into the container:

```yml
shared_files:
  - local_path: ${OCUDU_PATH}/build_retina/apps/gnb/gnb   # Required: Source path (absolute)
    remote_path: /usr/local/bin/gnb                       # Required: Destination path (absolute)
    is_executable: true                                   # Required: Grant execute permissions
```

**Note**: Files are **copied** into the container, not mounted.

## Custom Labels

Add Kubernetes labels to control pod placement. Labels are combined with Retina's default labels.

Example:

```yml
- name: mydev
  type: 5gc
  image: ${RETINA_REGISTRY_URI}/open5gs:${OPEN5GS_VERSION}_${RETINA_VERSION}
  requirements:
    cpu:
      requests: 1
    memory:
      requests: "4G"
    ephemeral-storage:
      requests: "3G"
      limits: "3G"
  labels:
    - "kubernetes.io/hostname=my-specific-node"
```

### Label Selection Priority

Retina selects nodes using the following priority:

1. **Hostname label** (`kubernetes.io/hostname`): If specified, forces pod to that specific node
2. **Resources**: Selects nodes with available matching hardware resources
3. **Other labels**: Uses any additional custom labels specified
