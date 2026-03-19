# E2E Testing Approach

## Test Types

We use retina in all e2e tests to: reserve and orchestrate the testbed, start and configure the ocudu binaries, parse logs, extract KPIs and more. However, we follow different strategies for the logic of the test itself.

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
│   ├── ue/
│   │   ├── handover.cfg
│   │   └── ...
│   ├── viavi/
│   │   ├── campaign.xml
│   │   └── ...
│   ├── gnb/
│   │   ├── 1t1r_bw10_band3.yml
│   │   └── ...
│   ├── core/
│   │   ├── baseline.cfg
│   │   └── ...
├── steps/
│   ├── configuration.py
│   └── ...
├── suites/
│   ├── functional/
│   │   ├── mobility/
│   │   │   ├── inter_ru_ho.yml
│   │   │   └── ...
│   │   ├── multiue/
│   │   │   ├── ping.yml
│   │   │   └── ...
│   ├── performance/
│   └── ...
|── # Test Templates
|── amarisoft_simulator.py
|── viavi_simulator.py
|── iperf.py
└── ...
```

## Test Templates

Located at `ocudu_infra_srs/e2e/tests/`:

my test_template.py

```python
@pytest.mark....
def test(*args, **kwargs): # Receives parameters from the tests
    pass # Call functions defined in "steps", so we can reuse it between test cases.
```

## Tests Suites

Located at `ocudu_infra_srs/e2e/tests/suites`:

pipeline_name/stage_name/job_name.yml

```yml
example: # Test Case
  # Selecting the test template
  template: ue_simulator.test_gnb
  # Selecting the retina request
  testbed: zmq_mme
  # Feature IDs covered in this test
  feature_ids: [MVP-FUNC-MOB-1-b, MVP-FUNC-MOB-1-c, MVP-FUNC-MOB-14]
  # Configs and parameters for each item
  ue:
    config: [2cell_2t2r_bw100_band78_chsim.cfg, handover.cfg]
    parameters:
      nof_antennas: 2
  gnb:
    config:
      [2t2r_bw100_band78.yml, base_slice.yml, pcaps.yml, 2cell_intradu_ho.yml]
  core:
    config: [baseline.cfg]
  # Adding pass/fail criteria to the test
  criteria:
    dl_bitrate: 10.0e+6
    ul_bitrate: 10.0e+6
    errors: 0
    warnings: 0
```

## CI

Please run `ocudu_infra_srs/e2e/scripts/generate_pipelines.py` to update the CI files after any change in the `suites` folder. MR CI will enforce that everything is up-to-date.
