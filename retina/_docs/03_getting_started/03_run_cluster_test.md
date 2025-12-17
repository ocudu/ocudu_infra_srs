# Run a Retina Test in the Testing Cluster

## Pre requisite

You should have [installed](./01_installation.mdx) the framework according to previous chapters.

## 1. Setup environment

### 1.1 Create variables file

```bash
cd ocudu_infra_srs # where you checked out this repo
cd e2e/retina_requests
python3 ../../retina/_scripts/generate_env.py --ocudu-path ~/workspace/ocudu
```

Review the variables defined in `ocudu_infra_srs/e2e/retina_requests/.env`, specially `OCUDU_PATH`

### 1.2 Build ocudu binaries

For the OCUDU binaries, you can download them from the CI or [build them in local](../../_scripts/run_tests.md#3-build-ocudu-apps-and-zmq-driver).

## 2. Running the test

```bash
cd ocudu_infra_srs/e2e
retina-launcher --retina-request=./retina_requests/<testbed>.yml ...
```

- retina-request: This file defines the items we need in our test (UE, CU, DU, 5GC, etc.) and their resources (cpu, ram, SDRs, etc.). Retina will read it to orchestrate the test infrastructure.
- To select a test, [pytest](https://docs.pytest.org/) provides different alternatives.

You can check the output of a CI job to get the retina-launcher command line call.

## Troubleshooting

### No configuration found

```txt
  File "/usr/local/lib/python3.10/dist-packages/kubernetes/config/kube_config.py", line 770, in _get_kube_config_loader
    raise ConfigException(
kubernetes.config.config_exception.ConfigException: Invalid kube-config file. No configuration found.
```

Make sure that your kubernetes config file (`/home/your_user/.kube/config`) is correct. You can customize the kubernetes config by using:

- `KUBECONFIG`: Alternative path for kube config
- `KUBECONFIG_EXTRA`: Additional config to add to your existing main config (via variable or default path)
- `KUBECONFIG_CONTEXT`: Select a specific context from your config
