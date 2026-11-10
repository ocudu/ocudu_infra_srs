# IaC Full Example

This folder contains a full example of a cluster defined in IaC. It covers the following testbeds:

## Gitlab runners

```mermaid
---
config:
    theme: neutral
---
graph LR
    subgraph cluster
        subgraph untagged
            glr_untagged_pod
        end
        subgraph builder
            glr_build_pod
        end
        subgraph retina
            glr_retina_pod
        end
    end
```

- 1 PC/VM for building OCUDU
- 1 PC/VM for untagged jobs
- 1 PC/VM for running Retina Tests

## ZMQ Testbed

```mermaid
---
config:
    theme: neutral
---
graph LR
    subgraph cluster
        subgraph zmq_server
            retina_ue_pods <-->|zmq| retina_gnb_pods
            retina_gnb_pods <--> retina_core_pods
        end
    end
```

- 1 Server to run one or multiple ZMQ tests

## s72 Testbed

An S72 testbed runs the OCUDU split 7.2 gNB against an Amarisoft UE Simulator (UESIM). In the standard deployment, both machines are Kubernetes nodes: Retina schedules the gNB on the gNB node and the UE simulator and core on the UESIM node. The S72 fronthaul is a dedicated Layer-2 network; N2/N3 traffic uses the normal backhaul network.

```mermaid
---
config:
    theme: neutral
---
graph LR
    subgraph cluster
        subgraph gnb_server[gnb node]
            retina_gnb_pod[retina gNB pod]
        end
        subgraph uesim_server[UESIM node]
            retina_ue_pod[retina UE pod]
            retina_core_pod[retina core pod]
        end
    end
    retina_gnb_pod <-->|N2/N3 backhaul| retina_core_pod
    retina_gnb_pod <-->|S72 fronthaul<br/>two VLANs| fh_switch[PTP fronthaul switch<br/>GPS grandmaster]
    fh_switch <-->|S72 fronthaul<br/>two VLANs| retina_ue_pod
```

For the full host, network, timing and Retina setup, see the [S72 testbed guide](testbeds/s72.md).

## RF Testbed

```mermaid
---
config:
    theme: neutral
---
graph LR
    subgraph cluster
        subgraph rf_server
            retina_gnb_pod <--> sdr
        end
    end
    callbox <--> retina_gnb_pod
    cots_phone <-->|air| sdr
```

- 1 Server to run OCUDU, with a SDR
- 1 COTS Phone
- 1 Core (outside of the cluster)
