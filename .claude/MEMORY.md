# Project Memory

## Pcap Filters

See [pcap_filters.md](pcap_filters.md) for full details on how to add a new pcap filter and criteria.

### Quick reference
- Analyzer base class: `retina/agent/src/retina/agent/features/pcap/analyzer.py`
- RRC analyzers: `retina/agent/src/retina/agent/features/pcap/rrc.py`
- Criteria registration: `retina/launcher/src/retina/launcher/public.py` → `_register_du_criteria()`
- Helper for mac pcap lookup: `_prach_config_index_from_mac_pcap()` in `public.py`
