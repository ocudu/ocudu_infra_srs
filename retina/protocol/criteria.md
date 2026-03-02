# How to Add a New Criteria

| Step | Where | What to do |
| ---- | ---- | ---------- |
| 1 | [base.proto](./src/retina/protocol/base.proto) | Add field to `Metrics` |
| 2a | [json metric analyzer](../agent/src/retina/agent/features/json_metrics/__init__.py) | Improve/create a `JsonMetricsAnalyzer` and register it in the driver |
| 2b | [pcap analyzer](../agent/src/retina/agent/features/pcap/__init__.py) | Improve/create a `PcapAnalyzer` and register it in the driver |
| 3 | [launcher code](../launcher/src/retina/launcher/public.py#_register_du_criteria) | Add `register_available_criteria` call |
| 4 | test_file.yml | Add it to the `criteria` section |

## 1. Add the field to `Metrics` in `base.proto`

Add the new field to the `Metrics` message in [base.proto](./src/retina/protocol/base.proto) with the next available field number:

```protobuf
message Metrics {
  ...
  uint32 nof_mew_metric = 18;  // next free number after ue_array = 17
};
```

**Rules:**

- Never reuse a field number, even for removed fields.
- Use the smallest numeric type that fits (`uint32` for counters, `double` for rates).
- If the metric is per-UE rather than aggregate, add it to `UeMetrics` instead.

Then regenerate the Python bindings:

```bash
cd retina/protocol && tox -e grpc
```

## 2. Populate the field in the agent

### 2a. JSON WebSocket

Analyzers are located at the [agent code](../agent/src/retina/agent/features/json_metrics/__init__.py)

**If the new field fits naturally in an existing analyzer**, add it to an existing one, f.e.:
`retina/agent/src/retina/agent/features/json_metrics/du_general.py`:

```python
# inside GeneralMetricsAnalyzer.process(), in the cell_metrics block:
self._metrics.nof_mew_metric += cell_info["cell_metrics"]["mew_metric"]
```

**If the new field warrants its own file** (e.g. it has non-trivial state), create it and implement JsonMetricsAnalyzer:
`retina/agent/src/retina/agent/features/json_metrics/new_metric_parser.py`:

```python
from retina.protocol.base_pb2 import Metrics
from retina.agent.features.json_metrics.analyzer import JsonMetricsAnalyzer

class NewAnalyzer(JsonMetricsAnalyzer):
    def __init__(self) -> None:
        self._count = 0

    def process(self, metric_info: dict) -> None:
        for cell_info in metric_info.get("cells", []):
            if "cell_metrics" in cell_info and cell_info["cell_metrics"]:
                self._count += cell_info["cell_metrics"]["mew_metric"]

    def report(self) -> Metrics:
        return Metrics(nof_mew_metric=self._count)
```

Then register the new analyzer in the driver (f.e. `retina/agent/src/retina/agent/drivers/ocudu_du.py` for du metrics):

```python
from retina.agent.features.json_metrics.new_metric_parser import NewAnalyzer

_WS_ANALYZER_ARRAY = (GeneralMetricsAnalyzer, PerUePeakAverageAnalyzer, NewAnalyzer)
```

### 2b. PCAP

Use this when the data comes from packet captures.

Create a new analyzer at the [agent code](../agent/src/retina/agent/features/pcap/__init__.py)

```python
# retina/agent/features/pcap/new_metric.py
from retina.protocol.base_pb2 import Metrics
from retina.agent.features.pcap.analyzer import PcapAnalyzer

class NewAnalyzer(PcapAnalyzer):
    def __init__(self) -> None:
        self._count = 0

    @property
    def tshark_params(self):
        return ("--enable-heuristic", "rlc_nr_udp")

    @property
    def display_filter(self) -> str:
        return "nr-rrc.rachConfigCommon_element"  # example filter

    def process(self, packet) -> None:
        self._count += 1

    def report(self) -> Metrics:
        return Metrics(nof_mew_metric=self._count)
```

Then add it to the driver, f.e. in `ocudu_du.py`:

```python
from retina.agent.features.pcap.rach import NewAnalyzer

_RLC_PCAP_ANALYZER_ARRAY = (ReestablishmentAnalyzer, HandoverAnalyzer, NewAnalyzer)
```

## 3. Register the criteria in the launcher

File: `retina/launcher/src/retina/launcher/public.py`, function `_register_du_criteria()`.

Add a `register_available_criteria` call in the [launcher code](../launcher/src/retina/launcher/public.py#_register_du_criteria) with:

- **`criteria_id`**: snake_case key used in tests to activate this criterion. Use same name than the metric field to make the mapping easier.
- **`name`**: human-readable label shown in the pass/fail table.
- **`callback`**: lambda that calls `GetMetrics` and returns the scalar value to compare.
- **`operator_method`**: comparison direction (`operator.le` for "must be ≤", `operator.gt` for
  "must be >", `operator.eq` / `operator.ge` for exact/minimum counts).

```python
criteria.register_available_criteria(
    "nof_mew_metric",
    "New metric",
    lambda: sum(gnb_stub.GetMetrics(Empty()).nof_mew_metric for gnb_stub in du_or_gnb_array),
    operator.le,
)
```

## 4. Use the criteria in a test

When defining the test case, write down the criteria_id and the expected value.

```yml
baseline:
  template: ...
  criteria:
    nof_mew_metric: 17
```
