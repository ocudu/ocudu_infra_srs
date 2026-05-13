# E2E Testing Approach

## Test Types

We use [retina](../../retina/README.md) in all e2e tests to: reserve and orchestrate the testbed, start and configure the ocudu binaries, parse logs, extract KPIs and more. However, we follow different strategies for the logic of the test itself.

* Use retina gRPC methods. The test case is written using pytest and we call the grpc methods for every step we want to do in the test (do a ping, iperf, stop, etc.)
* Use a simulator: In this case, retina just starts the ocudu binaries and the simulator. The test case is defined in the simulator format:
  * Amarisoft: The events are defined in the config files for Amarisoft LTE and MME.
  * Viavi: Test cases and campaigns are defined in xml files.

## Legend

| Name | Description |
|------|-------------|
| Testbed | Where the test is going to run. It's defined in a retina request file and it tells retina what it needs to orchestrate for the test: physical HW and resources (sdrs, ...), containers and their resources (cpu, ram, ...), licenses, etc. |
| OCUDU configs | Configuration files for OCUDU binaries. We'll use them (one or multiple) in the tests. |
| Test Template | It defines a test skeleton that contains the steps the test will do. It's generic (use a generic ue, cu, etc). Multiple test cases (each one with a different setting and configuration) will use the same template. |
| Test Step | Each one of the steps a test template can use. Those steps are reusable between test templates. |
| Test Case | The final test case that runs by combining a test template (and a simulator test), ocudu configurations and testbed. |
| Test Suite | A collection of test cases. In our structure: each file is a test suite and it's mapped to one CI job. Folder structure maps CI stages and pipelines. |

## General structure

```text
ocudu_infra_srs/e2e/tests/
├── configs/
│   ├── ue/             # UE config files (Amarisoft UE, etc.)
│   │   ├── handover.cfg
│   │   └── ...
│   ├── viavi/
│   │   ├── campaign.xml
│   │   └── ...
│   ├── gnb/            # gNB config overlays (OCUDU)
│   │   ├── cell_cfg.yml
│   │   └── ...
│   ├── core/           # Core network config files (Amarisoft MME, Open5gs, etc.)
│   │   ├── baseline.cfg
│   │   └── ...
├── criterias/          # Pass/fail criteria definitions (one .py file per component)
│   ├── du.py
│   ├── core.py
│   ├── cu_cp.py
│   ├── cu_up.py
│   ├── gnb.py
│   ├── all.py          # Aggregates across all components
│   └── ...
├── steps/
│   ├── configuration.py
│   ├── stub.py
│   ├── test_loader.py
│   └── ...
├── suites/
│   ├── functional/
│   │   ├── singleue/
│   │   │   ├── slicing.yml
│   │   │   └── ...
│   │   ├── multiue/
│   │   │   ├── ping.yml
│   │   │   └── ...
│   │   ├── mobility/
│   │   │   ├── inter_ru_ho.yml
│   │   │   └── ...
│   └── performance/
│       └── mobility/
│           ├── paging.yml
│           └── ...
├── # Test Templates
├── ue_simulator.py
├── viavi_simulator.py
```

## Test Templates

Located at `ocudu_infra_srs/e2e/tests/`:

```python
@pytest.mark....
def test(*args, **kwargs): # Receives parameters from the tests
    pass # Call functions defined in "steps", so we can reuse it between test cases.
```

## Tests Suites

Located at `infra_srs/e2e/tests/suites`:

`pipeline_name/stage_name/job_name.yml`

```yml
baseline: &base_config # Test Case
  # Selecting the test template
  template: ue_simulator.test_gnb
  # Selecting the retina request (testbed definition from retina_requests/)
  request: zmq_mme
  # Feature IDs covered in this test
  feature_ids: [MVP-FUNC-MOB-1-b, MVP-FUNC-MOB-1-c, MVP-FUNC-MOB-14]
  # Configs and parameters for each item
  ue:
    config: [2cell_intrafreq_chsim.cfg, handover.cfg]  # Jinja2 .cfg files, merged in order
    parameters:
      nof_ue: 1
      test_duration: 100
  gnb:
    config: [cell_cfg.yml, 2cell_intrafreq.yml, mobility.yml, tdd_default.yml]  # YAML overlays, merged in order
  core:
    config: [baseline.cfg]
  # Pass/fail criteria: <component>.<metric_name>_<operator>: <threshold>
  criteria:
    du.dl_bitrate_gt: 0
    du.ul_bitrate_gt: 0
    du.nof_handovers_ge: 20
    all.errors_le: 0
    all.warnings_le: 0

# Additional test cases can extend a base config with YAML anchors
conditional_ho:
  <<: *base_config
  gnb:
    config: [cell_cfg.yml, 2cell_intrafreq.yml, mobility.yml, conditional_ho.yml]
  feature_ids: [MVP-FUNC-MOB-15]
```

## Criteria

### Naming convention

Criteria keys follow the pattern `<component>.<metric_name>_<operator>: <threshold>`.

| Component prefix | Source file | Metrics origin |
| --- | --- | --- |
| `du.*` | `criterias/du.py` | `ocudu_du.py` driver via gRPC `GetMetrics` |
| `core.*` | `criterias/core.py` | `amarisoft_5gc.py` / `open5gs_5gc.py` driver via gRPC `GetMetrics` |
| `cu_cp.*` | `criterias/cu_cp.py` | `ocudu_cu_cp.py` driver via gRPC `GetMetrics` |
| `cu_up.*` | `criterias/cu_up.py` | `ocudu_cu_up.py` driver via gRPC `GetMetrics` |
| `gnb.*` | `criterias/gnb.py` | `ocudu_gnb.py` driver via gRPC `GetMetrics` |
| `all.*` | `criterias/all.py` | Aggregated sum across all component drivers |

Supported operators: `_gt` `(>)`, `_ge` `(>=)`, `_le` `(<=)`, `_eq` `(==)`.

### How criteria are implemented

Each criterion is a Python class in the corresponding `criterias/<component>.py` file. The class name is `<metric_name>_<operator>`, it declares `operator_method` (a `operator.*` function) and a `callback()` that calls gRPC to read the live metric value. The framework compares `callback()` against the threshold using `operator_method`.

```python
# criterias/core.py
class nof_pdu_session_establishment_accept_eq(FiveGcCriteria):
    operator_method = operator.eq

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).core.nof_pdu_session_establishment_accept for s in self._stub_array)
```

To know more about how to add a new Metric to Retina, check the [Metrics documentation](../../retina/protocol/criteria.md)

### Advanced criteria

Some criteria accept a list or an object instead of a scalar. The criteria implements the callback function to interpret this input. F.e.:

```yml
criteria:
  du.dl_ue_avg_bitrate:
    - id: 1
      value: 42.0e+6
    - id: 2
      value: 14.0e+6
```

## Config files

* All configuration files are Jinja2 templates, rendered at test start.
* Variables come from the `parameters:` block in the suite YAML and from [Retina parameters](../../retina/agent/src/retina/agent/parameters/__init__.py).
* Multiple files are merged in list order; later files override earlier ones.
* Folders:
  * UE configs (`configs/ue/`)
  * gNB / DU / CU / CU-UP / CU-CP configs (`configs/gnb/*.yml`)
  * Core configs (`configs/core/*.cfg`)

## CI

Please run `ocudu_infra_srs/e2e/scripts/generate_pipelines.py` to update the CI files after any change in the `suites` folder. MR CI will enforce that everything is up-to-date.

The generated files (`e2e/functional-config.yml` and `e2e/performance-config.yml`) define one GitLab CI job per test suite file and must not be edited manually.
