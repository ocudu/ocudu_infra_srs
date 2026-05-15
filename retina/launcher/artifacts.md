# Retina Test Artifacts

This document describes the artifact structure produced by the Retina launcher after an E2E test run.

## Top-level structure

```text
<log_dir>/                                    # e.g. ocudu_infra_srs/e2e/log/
├── report.html                               # pytest-html report: all tests, pass/fail, links to per-test artifacts
└── tests/
    └── <test_file>.py/                       # e.g. ue_simulator.py
        └── <test_name>[<suite.param>]/       # e.g. test_gnb[functional.singleue.tdd_siso.baseline_gnb]
            ├── test.html                     # HTML index of this test folder (browser navigation)
            ├── testbed.json                  # Testbed topology used for this test
            └── <item>/                       # One folder per network element (gnb, ue, 5gc, cu, du, ...)
```

## Entry point

**`report.html`** — start here when browsing results. It is a pytest-html report listing all test cases with their outcome and a link to each test's artifact folder.

## Per-test folder

### `testbed.json`

Python dict (pretty-printed) mapping each network element type (`gnb`, `ue`, `5gc`, `cu`, `du`, ...) to node names with their IP address and gRPC port. Useful for understanding the topology and identifying which machines were used.

```json
{
  "gnb": {"ocudu-gnb-1-1": {"address": "172.20.0.20", "port": 50051}},
  "ue":  {"amarisoft-ue-1": {"address": "172.20.0.10", "port": 50064}},
  "5gc": {"amarisoft-5gc-1-1": {"address": "172.20.0.71", "port": 50051}}
}
```

### `test.html`

HTML rendering of the test folder for browser navigation. Not useful for analysis.

## Per-item folder (`<item>/`)

Each network element involved in the test (e.g. `ocudu-gnb-1-1`, `amarisoft-ue-1`, `amarisoft-5gc-1-1`) has its own folder with this layout:

```text
<item>/
├── agent-log-<timestamp>.log     # Retina agent log — check this first
└── <timestamp>/                  # One subfolder per binary invocation
    ├── stdout.log                # Binary stdout
    ├── ps_info_<proc>.txt        # Process snapshot (CPU/RAM)
    ├── <binary>.log              # Full binary log (gnb.log, ue.log, mme.log, ...)
    ├── metrics.json              # Per-second metrics collected by Retina
    ├── *.yml / *.cfg             # Config files used in this invocation
    └── *.pcap                    # Packet captures — gnb only (mac.pcap, rlc.pcap)
```

> **Note:** Every file also has an `.html` twin (e.g. `gnb.log.html`). These are HTML renderings of the same content for browser viewing. Ignore them when reading files directly — always read the raw file.

### Recommended analysis order

1. **`agent-log-<timestamp>.log`** — short file, read first. Contains:
   - The exact binary command executed (`CMD executed: gnb -c ...`). It helps to identify the config file used.
   - Warnings and errors raised during the run (extracted from `<binary>.log`)
   - Post-run PCAP and metrics analysis results (retina analyzers output)

2. **`<timestamp>/stdout.log`** — binary stdout. Contains startup messages, crash backtraces, and assertion failures. Also contains periodic traffic tables (rows of DL/UL throughput) which are **less useful for functional analysis than the metrics.json** — skip those sections.

3. **`<timestamp>/<binary>.log`** — full verbose log (`gnb.log`, `ue.log`, `mme.log`, ...). Usually large. Read only after narrowing down the issue from `agent.log` and `stdout.log`.

4. **`<timestamp>/metrics.json`** — Contains structured per-second metrics reported by the binary and collected by Retina (MAC latency, PRB usage, cell KPIs, etc.). Useful for performance analysis or verifying specific behaviors over time.

5. **`<timestamp>/ps_info_<proc>.txt`** — a `ps` snapshot of the binary process. Useful for CPU/RAM usage analysis; usually not relevant for functional issue investigation.

6. **`<timestamp>/*.yml` / `*.cfg`** — exact config files passed to the binary. Cross-reference with the `CMD executed:` line in `agent.log` to identify which config was active.

7. **`<timestamp>/*.pcap`** — packet captures. Referenced by retina's PCAP analyzers whose output appears in `agent.log`. Open with Wireshark for deep protocol inspection.

## Item naming conventions

| Prefix           | Element                    |
| ---------------- | -------------------------- |
| `ocudu-gnb-*`    | OCUDU combined CU+DU gNB   |
| `ocudu-cu-*`     | OCUDU CU (split mode)      |
| `ocudu-cu-cp-*`  | OCUDU CU-CP                |
| `ocudu-cu-up-*`  | OCUDU CU-UP                |
| `ocudu-du-*`     | OCUDU DU (split mode)      |
| `amarisoft-ue-*` | Amarisoft UE simulator     |
| `amarisoft-5gc-*`| Amarisoft 5G core (MME)    |
| `open5gs-*`      | Open5Gs core               |

The suffix `-<rack>-<index>` (e.g. `-1-1`) identifies the rack and instance number within that rack.
