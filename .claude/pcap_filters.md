# Pcap Filters — How to Add a New One

## Architecture

```
retina/agent/src/retina/agent/features/pcap/
├── analyzer.py      # PcapAnalyzer base class + run_analyzers()
└── rrc.py           # Concrete analyzers: HandoverAnalyzer, ReestablishmentAnalyzer, PrachConfigIndexAnalyzer
```

There are two kinds of pcap files the DU produces:
- **RLC pcap** (`rlc.pcap`) — uses heuristic dissector. Enabled with `rlc_enable: true` in gnb config.
- **MAC pcap** (`mac.pcap`) — standard NR-RRC dissection. Enabled with `mac_pcap_enable: true` in gnb config (or `mac_enable: true` in gnb_defaults).

### PcapAnalyzer base class (analyzer.py)

```python
class PcapAnalyzer(ABC):
    @property
    def tshark_params(self) -> Tuple[str, ...]:
        return ()   # Override for RLC: return "--enable-heuristic", "rlc_nr_udp"

    @property
    def display_filter(self) -> str:
        return ""   # tshark display filter, e.g. "nr-rrc.prach_ConfigurationIndex"

    @abstractmethod
    def process(self, packet) -> None: ...   # called per matching packet

    @abstractmethod
    def report(self) -> Metrics: ...         # called once at end
```

`run_analyzers(pcap_file, analyzers)` runs all analyzers and returns merged `Metrics`.

---

## Two integration patterns

### Pattern A — result via gRPC Metrics proto (RLC pcap)
Used by: `HandoverAnalyzer`, `ReestablishmentAnalyzer`

1. Add field to `retina/protocol/src/retina/protocol/base.proto` + regenerate `base_pb2.py` (run `tox -e grpc` in `retina/protocol/`)
2. `report()` returns `Metrics(new_field=value)`
3. Add analyzer to `_RLC_PCAP_ANALYZER_ARRAY` in `retina/agent/src/retina/agent/drivers/ocudu_du.py`
4. In `public.py`, lambda calls `gnb_stub.GetMetrics(Empty()).new_field`

### Pattern B — via proto Metrics + agent driver (MAC pcap)
Used by: all MAC pcap analyzers (`PrachConfigIndexAnalyzer`, `SibAnalyzer`, etc.)

MAC pcap analysis runs in the agent (same as RLC). Results go through `GetMetrics()` gRPC.

1. Add proto field to `base.proto` + regenerate (`tox -e grpc` in `retina/protocol/`)
2. `report()` returns `Metrics(field=self._value)` (use `int32` for config values, `uint32` for counts)
   - Config value analyzers: init with `-1` (not found). `report()` always returns the value, even -1.
   - Counter analyzers: init with `0`. `report()` returns `Metrics(field=self._count)`.
3. Add analyzer to `_MAC_PCAP_ANALYZER_ARRAY` in `retina/agent/src/retina/agent/drivers/ocudu_du.py`
4. In `public.py`, lambda calls `s.GetMetrics(Empty()).field` — no `report_folder` needed

---

## Step-by-step: add a new MAC pcap filter (Pattern B)

### 1. Add proto field to `base.proto`

```protobuf
message Metrics {
  ...
  int32 my_new_field = N;  // use next free field number
}
```

Then regenerate: `cd retina/protocol && tox -e grpc`

Notes:
- Use `uint32` for counters (0 = none found)
- Use `int32` for config values (-1 = not found/not captured)

### 2. Add analyzer to `rrc.py`

```python
class MyNewAnalyzer(PcapAnalyzer):
    def __init__(self) -> None:
        self._value: int = -1

    @property
    def display_filter(self) -> str:
        return "nr-rrc.some_Field"   # tshark display filter

    def process(self, packet) -> None:
        if self._value < 0:
            try:
                self._value = int(packet["NR-RRC"].some_field)
            except (AttributeError, KeyError, ValueError):
                pass

    def report(self) -> Metrics:
        return Metrics(my_new_field=self._value)
```

Notes:
- Field name in pyshark: lowercase, no hyphens/dots (e.g. `nr-rrc.prach_ConfigurationIndex` → `packet["NR-RRC"].prach_configurationindex`)
- No `tshark_params` needed for MAC pcaps (unlike RLC which needs `"--enable-heuristic", "rlc_nr_udp"`)

### 3. Register analyzer in `ocudu_du.py`

```python
from retina.agent.features.pcap.rrc import ..., MyNewAnalyzer

_MAC_PCAP_ANALYZER_ARRAY = (
    ...,
    MyNewAnalyzer,
)
```

### 4. Add criteria in `public.py`

Inside `_register_du_criteria()`:
```python
criteria.register_available_criteria(
    "my_criteria_eq",
    "My Criteria Display Name",
    lambda: sum(s.GetMetrics(Empty()).my_new_field for s in du_or_gnb_array),
    operator.eq,
)
```

### 5. Use in YAML test suite

```yaml
my_test:
  gnb_parameters:
    mac_pcap_enable: true
  criteria:
    my_criteria_eq: 42
```

---

## Key file paths

| File | Purpose |
|------|---------|
| `retina/agent/src/retina/agent/features/pcap/rrc.py` | All RRC-layer pcap analyzers |
| `retina/agent/src/retina/agent/features/pcap/analyzer.py` | Base class + `run_analyzers()` |
| `retina/agent/src/retina/agent/drivers/ocudu_du.py` | DU driver — calls pcap analysis on stop, merges into `self._metrics` |
| `retina/launcher/src/retina/launcher/public.py` | Criteria registration (`_register_du_criteria`) |
| `retina/protocol/src/retina/protocol/base.proto` | Metrics proto definition |
| `retina/protocol/src/retina/protocol/base_pb2.py` | Generated proto (do NOT edit manually; run `tox -e grpc`) |
| `e2e/tests/suites/functional/singleue/phy_configs.yml` | Example test suite using MAC pcap criteria |

## Existing analyzers

| Class | File | pcap type | tshark filter | Proto field |
|-------|------|-----------|---------------|-------------|
| `HandoverAnalyzer` | `rrc.py` | RLC | `nr-rrc.reconfigurationWithSync_element` | `nof_handovers` |
| `ReestablishmentAnalyzer` | `rrc.py` | RLC | `nr-rrc.rrcReestablishmentRequest_element \|\| ...Complete_element` | `nof_reestablishments_request/complete` |
| `PrachConfigIndexAnalyzer` | `rrc.py` | MAC | `nr-rrc.prach_ConfigurationIndex` | `prach_configuration_index` (int32) |
| `SibAnalyzer` | `rrc.py` | MAC | `nr-rrc.sib{n}_element` for n in (1,2,3,4,5,8) | `nof_sib{n}_transmissions` (uint32) |
| `PagingAnalyzer` | `rrc.py` | MAC | `nr-rrc.paging_element` | `nof_paging_messages` (uint32) |
| `DrxLongCycleAnalyzer` | `rrc.py` | MAC | `nr-rrc.drx-LongCycleStartOffset` | `drx_long_cycle_start_offset` (int32) |
| `T312Analyzer` | `rrc.py` | MAC | `nr-rrc.t312` | `t312` (int32) |
| `TransformPrecoderAnalyzer` | `rrc.py` | MAC | `nr-rrc.transformPrecoder` | `transform_precoder` (int32) |
| `SrsFreqDomainAnalyzer` | `rrc.py` | MAC | `nr-rrc.c-SRS \|\| nr-rrc.b-SRS` | `c_srs`, `b_srs` (int32) |

## Criteria operators available
`operator.eq`, `operator.ge`, `operator.le`, `operator.gt`, `operator.lt`, `operator.ne`

## Driver flow (Pattern B MAC pcap)
`Stop()` → `get_metrics_parsing_arguments()` returns `(rlc.pcap, mac.pcap)` → `extract_metrics()` runs both `_RLC_PCAP_ANALYZER_ARRAY` and `_MAC_PCAP_ANALYZER_ARRAY` → results in `self._metrics` → returned by `GetMetrics()`.

## Timing note
Criteria lambdas are evaluated during `criteria.validate()`, which the test calls AFTER `stop()`.
By then, `Stop()` gRPC has been called on the agent, finalizing all pcap files locally.
MAC pcaps are at `{test_log_folder}/{component}/{timestamp}/mac.pcap`.
