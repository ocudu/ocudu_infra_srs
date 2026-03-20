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

```mermaid
---
config:
    theme: neutral
---
graph LR
    subgraph cluster
        subgraph gnb_server
            retina_gnb_pod <--> retina_core_pod
        end
    end
    retina_gnb_pod <-->|s72| uesim_box    
```

- 1 Server to run OCUDU
- 1 UE SimBox (outside of the cluster)

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
