# Use the booking system

Retina provides a system to manage the reservation of resources like PCs, licenses, SDRs, etc. You can reserve, release, and check the current status of these resources. When a resource is reserved, it ensures that no other user or external system (such as GitLab) can use it, avoiding potential conflicts.

```bash
$ retina --help
Usage: retina [OPTIONS] COMMAND [ARGS]...

  CLI for Retina system.

Options:
  --help  Show this message and exit.

Commands:
  release  Release a resource.
  reserve  Reserve a resource.
  status   Show all the resources in the cluster.
```

## Prerequisites

Before using these commands, ensure you have [installed](./03_installation.mdx) the Retina framework as per previous chapters.

## Viewing Resources

To view all available resources in the cluster:

```bash
$ retina status --help
Usage: retina status [OPTIONS]

  Show all the resources in the cluster.

Options:
  --verbose  Verbose mode
  --help     Show this message and exit.
```

To display the status of all cluster resources:

```bash
$ retina status
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃                Name ID ┃ Reserved by ┃ Resource type ┃ Resource model ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ amarisoft-5g-license:0 │             │ license       │ amarisoft-5g   │
│ amarisoft-5g-license:1 │             │ license       │ amarisoft-5g   │
└────────────────────────┴─────────────┴───────────────┴────────────────┘
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃    Node name ID ┃ Reserved by   ┃ IP        ┃ Architecture ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│      builder-pc │ gitlab-runner │ 10.12.0.1 │ amd64        │
│ k8s-worker-uhd3 │ gitlab-runner │ 10.12.0.2 │ amd64        │
│  k8s-worker-vm0 │ gitlab-runner │ 10.12.0.3 │ amd64        │
│  k8s-worker-vm1 │               │ 10.12.0.4 │ amd64        │
│   zmq-runner-pc │ ci_zmq        │ 10.12.0.5 │ amd64        │
│  k8s-worker-vm3 │ gitlab-runner │ 10.12.0.6 │ amd64        │
│  k8s-worker-vm4 │ gitlab-runner │ 10.12.0.7 │ amd64        │
└─────────────────┴───────────────┴───────────┴──────────────┘
```

This command is useful for checking the status of resources before reserving them, helping you identify which ones are free or currently in use. It also provides useful details like the IP addresses of the machines or their specifications.

### Amarisoft License Integration

Retina communicates with the Amarisoft License Server to check license availability before performing status and reservation operations. This helps users know whether licenses are available before attempting to use resources.

- Amarisoft License Server information will be reported in `retina status` command.
- The user can skip this license check by adding the `--skip-license-check` flag

## Resource Reservation

To reserve a resource, use the following command:

```bash
$ retina reserve --help
Usage: retina reserve [OPTIONS] RESOURCE

  Reserve a resource.

Options:
  --username TEXT                 Your username
  --verbose                       Verbose mode
  --image TEXT                    Image to use in the deployed container
  --help                          Show this message and exit.
```

For example, to reserve a specific resource:

```bash
$ retina reserve zmq-runner-pc
2024-10-09 16:05:55,507 [INFO] ⏳ Reserving resource zmq-runner-pc for user ranuser
2024-10-09 16:05:56,086 [INFO] ⏰ It may take up to 30 minutes, please be patient...
2024-10-09 16:05:57,003 [INFO] Looking for cluster resources...
2024-10-09 16:05:57,003 [INFO] Looking for node resources...
2024-10-09 16:05:58,282 [INFO] Creating deployment for: ...
2024-10-09 16:06:02,174 [INFO] ✅ Resource zmq-runner-pc successfully reserved.
```

- You can reserve multiple resources at once by listing them, separated by commas.
- Please use the ID provided in the `retina status` table.
- When reserving a PC, a container will be created into that PC to avoid other pods to be deployed there. You can use that container or use the PC as usual.

## Releasing Resources

To release a resource, use the following command:

```bash
$ retina release --help
Usage: retina release [OPTIONS] [RESOURCE]

  Release a resource.

Options:
  --username TEXT  It will release all the resources reserved by the user
  --help           Show this message and exit.
```

You can release specific resources as shown below:

```bash
retina release amarisoft-5g-license:0,zmq-runner-pc
```

Or release all the resources you have reserved:

```bash
$ retina release --username $USER
2024-10-09 16:06:20,488 [INFO] ⏳ Releasing resource amarisoft-5g-license:0
2024-10-09 16:06:22,409 [INFO] ✅ All resources reserved by user ranuser successfully released.
```

## Possible Warnings

If you are not using the latest version of Retina, you might see the following warning:

```text
2024-10-09 16:05:55,507 [WARNING] Please update Retina. Current package version: 0.50.0, latest version: 0.53.6
```
