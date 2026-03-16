# TuneD

Terraform module that deploys per-node [TuneD](https://tuned-project.github.io) agents onto a Kubernetes cluster using the [srsRAN tuned Helm chart](https://srsran.github.io/srsRAN_Project_helm).

Each enabled node gets its own `helm_release` (`tuned-<node-name>`) carrying a custom tuning profile and optional startup script.

## What it deploys

| Resource | Description |
| --- | --- |
| `helm_release` | One `tuned` release per node with `tuned.enabled: true` in `services.yaml` |

All releases are deployed into the `infra` namespace (must exist beforehand).

## `services.yaml` format

Node-level tuned configuration lives under `services.<node>.tuned`. Global defaults are read from `global.tuned` and can be overridden per node.

```yaml
global:
  tuned:
    image:
      repository: softwareradiosystems/tuned-agent
      tag: "0.5.0"
      pullPolicy: IfNotPresent
    hostPathTuned: /usr/lib/tuned
    securityContext:
      privileged: true
    resources: {}
    annotations: {}
    restartOnConfigChange: true
    nodeSelector: {}
    reboot:
      enabled: true
      cmd: /sbin/shutdown -r +1 'tuned profile applied by helm'
      markerDir: /var/lib/tuned-helm

services:
  my-node:
    tuned:
      enabled: true
      image:                    # optional — overrides global image
        tag: "0.5.0-arm64"
      profileContent: |-
        [main]
        summary=My tuned profile
        ...
      startupScriptContent: |-  # optional
        #!/bin/bash
        ...
      tolerations:              # optional — defaults to machine=<node>:NoSchedule
        - key: machine
          operator: Equal
          value: my-node
          effect: NoSchedule
```

## Inputs

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `services_file` | `list(string)` | required | Path(s) to the cluster `services.yaml` file |
| `helm_version` | `string` | `"0.5.0"` | Tuned Helm chart version |

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

module "tuned" {
  source        = "git::https://${var.infra_srs_path}.git//infrastructure/tuned?ref=${var.infra_srs_ref}"
  services_file = [abspath("${path.module}/../services.yaml")]
}
```

If the Helm releases already exist and need to be imported into state:

```hcl
import {
  to = module.tuned.helm_release.tuned["my-node"]
  id = "infra/tuned-my-node"
}
```

For CI template details see [opentofu.md](../_docs/04_opentofu.md).
