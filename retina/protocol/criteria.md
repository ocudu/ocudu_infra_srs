# How to Add a New Metric

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
  uint32 nof_new_metric = 18;  // next free number after ue_array = 17
};
```

**Rules:**

- Never reuse a field number, even for removed fields.
- Use the smallest numeric type that fits: `uint32` for counters (0 = none found), `int32` for config values (-1 = not found/not captured), `double` for rates.
- If the metric is per-UE rather than aggregate, add it to `UeMetrics` instead.

Then regenerate the Python bindings:

```bash
cd retina/protocol && tox -e grpc
```

## 2. Populate the field in the agent

- [OCUDU JSON metrics Reference](https://gitlab.com/ocudu/ocudu_docs/-/raw/main/docs/user_manual/outputs/outputs.md#json-metrics)
- [Amarisoft UE Metrics Reference](https://tech-academy.amarisoft.com/lteue.doc#LTE-messages-1)
- [Amarisoft MME Metrics Reference](https://tech-academy.amarisoft.com/ltemme.doc#Remote-API-1)

### 2a. JSON WebSocket

**If the new field fits naturally in an existing analyzer**, add it to an existing one, f.e.:
`retina/agent/src/retina/agent/features/json_metrics/du_general.py`:

```python
# inside GeneralMetricsAnalyzer.process(), in the cell_metrics block:
self._metrics.nof_new_metric += cell_info["cell_metrics"]["new_metric"]
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
                self._count += cell_info["cell_metrics"]["new_metric"]

    def report(self) -> Metrics:
        return Metrics(nof_new_metric=self._count)
```

Then register the new analyzer in the driver (f.e. `retina/agent/src/retina/agent/drivers/ocudu_du.py` for du metrics):

```python
from retina.agent.features.json_metrics.new_metric_parser import NewAnalyzer

_WS_ANALYZER_ARRAY = (GeneralMetricsAnalyzer, PerUePeakAverageAnalyzer, NewAnalyzer)
```

### 2b. PCAP

Use this when the data comes from packet captures.

[OCUDU PCAPs Reference](https://gitlab.com/ocudu/ocudu_docs/-/raw/main/docs/user_manual/outputs/outputs.md/#pcaps)

The DU produces two kinds of pcap files:

| pcap type | File | Enabled by |
| --- | --- | --- |
| **RLC pcap** | `rlc.pcap` | `rlc_enable: true` in gNB config |
| **MAC pcap** | `mac.pcap` | `mac_pcap_enable: true` in gNB config |

#### PcapAnalyzer base class

```python
class PcapAnalyzer(ABC):
    @property
    def tshark_params(self) -> Tuple[str, ...]:
        return ()   # Override for RLC: return ("--enable-heuristic", "rlc_nr_udp")

    @property
    def display_filter(self) -> str:
        return ""   # tshark display filter, e.g. "nr-rrc.prach_ConfigurationIndex"

    @abstractmethod
    def process(self, packet) -> None: ...   # called per matching packet

    @abstractmethod
    def report(self) -> Metrics: ...         # called once at end; return Metrics(field=value)
```

`run_analyzers(pcap_file, analyzers)` (in `analyzer.py`) runs all analyzers against the file and returns merged `Metrics`.

#### Implement your analyzer

```python
class MyNewAnalyzer(PcapAnalyzer):
    def __init__(self) -> None:
        self._value: int = -1   # use 0 for counters

    @property
    def display_filter(self) -> str:
        return "nr-rrc.some_Field"

    def process(self, packet) -> None:
        if self._value < 0:   # capture first occurrence
            try:
                self._value = int(packet["NR-RRC"].some_field)
            except (AttributeError, KeyError, ValueError):
                pass

    def report(self) -> Metrics:
        return Metrics(my_new_field=self._value)
```

> **pyshark field naming**: tshark display filter names (e.g. `nr-rrc.prach_ConfigurationIndex`) become lowercase with no hyphens/dots in pyshark (e.g. `packet["NR-RRC"].prach_configurationindex`).

#### Register it in `ocudu_du.py`

Add it to `_MAC_PCAP_ANALYZER_ARRAY` or `_RLC_PCAP_ANALYZER_ARRAY`

```python
from retina.agent.features.pcap.rrc import ..., MyNewAnalyzer

_MAC_PCAP_ANALYZER_ARRAY = (..., MyNewAnalyzer)
```

## 3. Register the criteria in the launcher

File: `retina/launcher/src/retina/launcher/public.py`, function `_register_du_criteria()`.

Add a `register_available_criteria` call in the [launcher code](../launcher/src/retina/launcher/public.py#_register_du_criteria) with:

- **`criteria_id`**: snake_case key used in tests to activate this criterion. Use same name as the metric field (plus the operator suffix) to make the mapping easier.
- **`name`**: human-readable label shown in the pass/fail table.
- **`callback`**: lambda that calls `GetMetrics` and returns the scalar value to compare.
- **`operator_method`**: comparison direction (`operator.le` for "must be ≤", `operator.gt` for "must be >", `operator.eq` / `operator.ge` for exact/minimum counts).

```python
criteria.register_available_criteria(
    "nof_new_metric_le",
    "New metric",
    lambda: sum(s.GetMetrics(Empty()).nof_new_metric for s in du_or_gnb_array),
    operator.le,
)
```

**Timing:** criteria lambdas are evaluated during `criteria.validate()`, which the test calls **after** `Stop()`. By then `Stop()` has been called on the agent, finalising all pcap files and populating `self._metrics` via `extract_metrics()`.

## 4. Use the criteria in a test

Check the [test documentation about criteria](../../e2e/tests/README.md#criteria)
