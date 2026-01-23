# Orchestrator

## Request file

Orchestrator's main input is the request file. In that file we write down what we need to deploy in the cluster. It's content is similar to the following example:

```yml
- name: ocudu-gnb
  type: gnb
  image: ${CI_REGISTRY_IMAGE}/retina/ocudu-gnb:${RETINA_VERSION}
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
  requirements:
    cpu:
      requests: 1
    memory:
      requests: "4G"
    ephemeral-storage:
      requests: "3G"
      limit: "3G"
  image: ${CI_REGISTRY_IMAGE}/retina/open5gs:${OPEN5GS_VERSION}_${RETINA_VERSION}
```

The format is:

- Array of pods (AKA a containers in a cluster) we want to create:
  - name `mandatory`: To identify it in the cluster, can be any string
  - image `mandatory`: Container image URI, from `registry.gitlab.com` or `hub.docker.com` (default docker registry).
  - type: `ue`, `gnb`, `5gc`. Ignore this field in development mode.
  - taints: [list of taints](#custom-taints)
  - labels: [list of labels](#custom-labels)
  - requirements:
    - cpu `mandatory`
      - requests `mandatory`: See [Requests vs limits](#requests-vs-limits) and [CPU](#cpu) sections below.
      - limits: See [Requests vs limits](#requests-vs-limits) and [CPU](#cpu) sections below.
    - memory `mandatory`
      - requests `mandatory`: See [Requests vs limits](#requests-vs-limits) and [Memory](#memory) sections below.
      - limits: See [Requests vs limits](#requests-vs-limits) and [Memory](#memory) sections below.
    - ephemeral-storage
      - requests `mandatory`: See [Requests vs limits](#requests-vs-limits) and [Ephemeral Storage](#ephemeral-storage) sections below.
      - limits: See [Requests vs limits](#requests-vs-limits) and [Ephemeral Storage](#ephemeral-storage) sections below.
  - resources: array of resources we want to book. Each item of the array has two fields:
    - type `mandatory`
    - model
  - shared_files: Array of items. Each shared path is **copied** into the container. Each item has following fields:
    - local_path `mandatory`: absolute path in your PC
    - remote_path `mandatory`: absolute path in the container.
    - is_executable `mandatory`: `true`/`false`. If `true`, executable rights are given.

### Requests vs limits

`requests` section defines the resource's quantity reserved exclusively for that pod. However, the pod can use more of that requirement (cpu, memory, etc) if available in the host. To limit the maximum quantity of a resource the pod can access to, you can set `limits`

[Read more at kubernetes documentation](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#requests-and-limits)

### CPU

- Field: `cpu`

Requests for CPU resources are measured in cpu units. In Retina, 1 CPU unit is equivalent to 1 physical CPU core, or 1 virtual core, depending on whether the node is a physical host or a virtual machine running inside a physical machine.

Fractional requests are allowed. When you define a container with `cpu` set to `0.5`, you are requesting half as much CPU time compared to if you asked for `1.0` CPU. For CPU resource units, the quantity expression `0.1` is equivalent to the expression 100m, which can be read as "one hundred millicpu". Some people say "one hundred millicores", and this is understood to mean the same thing.

CPU resource is always specified as an absolute amount of resource, never as a relative amount. For example, `500m` CPU represents the roughly same amount of computing power whether that container runs on a single-core, dual-core, or 48-core machine.

### Memory

- Field: `memory`

Limits and requests for memory are measured in bytes. You can express memory as a plain integer or as a fixed-point number using one of these quantity suffixes: E, P, T, G, M, k. You can also use the power-of-two equivalents: Ei, Pi, Ti, Gi, Mi, Ki. For example, the following represent roughly the same value:

```txt
128974848, 129e6, 129M,  128974848000m, 123Mi
```

Pay attention to the case of the suffixes. If you request `400m` of memory, this is a request for `0.4` bytes. Someone who types that probably meant to ask for 400 mebibytes (`400Mi`) or 400 megabytes (`400M`).

### Ephemeral Storage

- Field: `ephemeral-storage`

Requests for ephemeral-storage are measured in byte quantities. You can express storage as a plain integer or as a fixed-point number using one of these suffixes: E, P, T, G, M, k. You can also use the power-of-two equivalents: Ei, Pi, Ti, Gi, Mi, Ki. For example, the following quantities all represent roughly the same value:

- `128974848`
- `129e6`
- `129M`
- `123Mi`

Pay attention to the case of the suffixes. If you request `400m` of ephemeral-storage, this is a request for 0.4 bytes. Someone who types that probably meant to ask for 400 mebibytes (`400Mi`) or 400 megabytes (`400M`).

## Taints and labels

### Custom labels

The label "kubernetes.io/hostname=my-pc" will be added to the Retina labels.

```yml
- name: mydev
  type: 5gc
  requirements:
    cpu:
      requests: 1
    memory:
      requests: "4G"
    ephemeral-storage:
      requests: "3G"
      limit: "3G"
  image: ${CI_REGISTRY_IMAGE}/retina/open5gs:${OPEN5GS_VERSION}_${RETINA_VERSION}
  labels: ["kubernetes.io/hostname=my-pc"]
```

### Custom taints

It will override all the taints:

```yml
- name: mydev
  type: 5gc
  requirements:
    cpu:
      requests: 1
    memory:
      requests: "4G"
    ephemeral-storage:
      requests: "3G"
      limit: "3G"
  image: ${CI_REGISTRY_IMAGE}/retina/open5gs:${OPEN5GS_VERSION}_${RETINA_VERSION}
  taints: ["my-custom-taint"]
```
