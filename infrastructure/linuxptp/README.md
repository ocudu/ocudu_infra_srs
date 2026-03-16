# LinuxPTP

Terraform module that deploys per-node [linuxPTP](https://linuxptp.sourceforge.net) daemons onto a Kubernetes cluster using the [srsRAN linuxptp Helm chart](https://srsran.github.io/srsRAN_Project_helm).

Each enabled node gets its own `helm_release` (`linuxptp-<node-name>`) configured with the PTP interface and clock settings for that node.

## What it deploys

| Resource | Description |
| --- | --- |
| `helm_release` | One `linuxptp` release per node with `linuxptp.enabled: true` in `services.yaml` |

All releases are deployed into the `infra` namespace (must exist beforehand).

## `services.yaml` format

Node-level linuxptp configuration lives under `services.<node>.linuxptp`. Global defaults (image tag and `ptp4l` config) are read from `global.linuxptp` and can be overridden per node.

```yaml
global:
  linuxptp:
    image_tag: "v4.4_1.1.2"
    config:
      dataset_comparison: G.8275.x
      G.8275.defaultDS.localPriority: 128
      maxStepsRemoved: 255
      logAnnounceInterval: -3
      logSyncInterval: -4
      logMinDelayReqInterval: -4
      serverOnly: 0
      clientOnly: 1
      G.8275.portDS.localPriority: 128
      domainNumber: 24
      network_transport: L2
      delay_mechanism: E2E
      time_stamping: hardware
      clock_servo: linreg
      clockClass: 6
      clock_type: OC
      ts2phc:
        enabled: false

services:
  my-node:
    linuxptp:
      enabled: true
      interface_name: enp1s0f0np0
      image_tag: "v4.4_1.1.2-arm64"  # optional — overrides global image_tag
      config:                          # optional — merged on top of global config
        summary_interval: -3
```

Global and per-node `config` maps are shallow-merged (per-node keys take precedence). All `ptp4l` config fields, including keys with dots (e.g. `G.8275.defaultDS.localPriority`), are rendered safely via `yamlencode`.

## Inputs

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `services_file` | `list(string)` | required | Path(s) to the cluster `services.yaml` file |
| `helm_version` | `string` | `"1.3.0"` | Linuxptp Helm chart version |

## Using this module

Consumer `main.tf`:

```hcl
terraform {
  required_providers {
    helm = { source = "hashicorp/helm"; version = "~> 3.0" }
  }
  backend "http" {}
}

variable "infra_srs_path" { type = string }
variable "infra_srs_ref"  { type = string }

provider "helm" {}

module "linuxptp" {
  source        = "git::https://${var.infra_srs_path}.git//infrastructure/linuxptp?ref=${var.infra_srs_ref}"
  services_file = [abspath("${path.module}/../services.yaml")]
}
```

If the Helm releases already exist and need to be imported into state:

```hcl
import {
  to = module.linuxptp.helm_release.linuxptp["my-node"]
  id = "infra/linuxptp-my-node"
}
```

For CI template details see [opentofu.md](../_docs/04_opentofu.md).
