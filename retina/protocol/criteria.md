# How to Add a New Metric

| Step | Where | What to do |
| ---- | ---- | ---------- |
| 1 | [base.proto](./src/retina/protocol/base.proto) | Add field to `Metrics` |
| 2a | [json metric analyzer](../agent/src/retina/agent/features/json_metrics/__init__.py) | Improve/create a `JsonMetricsAnalyzer` and register it in the driver |
| 2b | [pcap analyzer](../agent/src/retina/agent/features/pcap/__init__.py) | Improve/create a `PcapAnalyzer` and register it in the driver |
| 3 | [criteria definitions](../../e2e/tests/criterias/__init__.py) | Add a `Criteria` subclass to `criterias/<component>.py` |
| 4 | test_file.yml | Add it to the `criteria` section |

## 1. Add the field to `Metrics` in `base.proto`

`Metrics` holds one message per component, so add the new field to the one of the component reporting it in
[base.proto](./src/retina/protocol/base.proto), with the next available field number of that message:

```protobuf
message DuMetrics {
  ...
  uint32 nof_new_metric = 31;  // next free number of DuMetrics
};
```

**Rules:**

- Never reuse a field number, even for removed fields. They are per message, so every message has its own count.
- Use the smallest numeric type that fits: `uint32` for counters (0 = none found), `int32` for config values (-1 = not found/not captured), `double` for rates.
- `UeMetrics` is used both per UE (`ue_array`) and for the whole testbed (`aggregate`).

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

## 3. Add the criteria class

File: `e2e/tests/criterias/<component>.py`, one file per component (`du.py`, `core.py`, `cu_cp.py`, `cu_up.py`, `gnb.py`, `all.py`).

Subclass the base class of the component (`DuCriteria`, `FiveGcCriteria`, ...). No registration call is needed:
`__init_subclass__` collects every subclass, and the launcher instantiates them all against the stubs of the
testbed.

```python
# criterias/du.py
class nof_new_metric_le(DuCriteria):
    """New metric"""

    operator_method = operator.le

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).du.nof_new_metric for s in self._stub_array)
```

- **class name**: the key used in tests, `<metric_name>_<operator>`. Together with the file name it forms the
  criteria id: `criterias/du.py` + `nof_new_metric_le` → `du.nof_new_metric_le`. Use the same name as the metric
  field plus the operator suffix to make the mapping easier.
- **docstring**: human-readable label shown in the pass/fail table.
- **`operator_method`**: comparison direction (`operator.le` for "must be ≤", `operator.gt` for "must be >",
  `operator.eq` / `operator.ge` for exact/minimum counts).
- **`callback()`**: reads the metric from `self._stub_array` and returns the value to compare. The value
  declared in the yml is in `self._input`, for the criteria interpreting a list or an object instead of a
  scalar (see `dl_ue_avg_bitrate`).

Every criteria class has to be used by at least one test: `scripts/static_checks.py` fails on unused ones.

**Timing:** `callback()` is called during `criteria.validate()`, which the test calls **after** `Stop()`. By
then `Stop()` has been called on the agent, finalising all pcap files and populating `self._metrics` via
`extract_metrics()`.

## 4. Use the criteria in a test

Check the [test documentation about criteria](../../e2e/tests/README.md#criteria)
