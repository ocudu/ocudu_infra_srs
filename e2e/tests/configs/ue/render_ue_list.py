#!/usr/bin/env python3

# Render ue_list.cfg.jinja into a UE configuration file.

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# ==== Configuration ====
traffic_type = "udp_bi"          # Type of traffic to generate. Values: "udp_dl", "udp_ul", "udp_bi, "ping"

base_imsi = int("1010123456789", 10)
base_K = int("00112233445566778899aabbccddeeff", 16)
base_power_on = 0                # Time at which first UE is powered on
power_on_increment = 0.1         # Time diff (to prev UE) at which next UE is powered on
nof_ues = 512                    # Total number of UEs to generate
power_on_to_traffic_delay = 10   # Time from power on to traffic start
traffic_duration_sec = 60        # Duration of traffic in seconds
traffic_stop_to_dereg_delay = 20 # Time from traffic stop to deregistration
dereg_to_pw_off_delay = 5        # Time from deregistration to power off
brate_dl = 800000                # Bitrate of CBR traffic in bps
brate_ul = 350000                # Bitrate of CBR traffic in bps
ue_start_index = 1

if traffic_type == "udp_dl":
    output_file = "multiue_udp_dl.cfg"
elif traffic_type == "udp_ul":
    output_file = "multiue_udp_ul.cfg"
elif traffic_type == "udp_bi":
    output_file = "multiue_udp_bi.cfg"
elif traffic_type == "ping":
    output_file = "multiue_ping.cfg"
# ========================

env = Environment(loader=FileSystemLoader(Path(__file__).parent), keep_trailing_newline=True)
env.filters["hex32"] = lambda v: format(int(v), "032x")
    
template = env.get_template("ue_list.cfg.jinja")
output = template.render(
    base_imsi=base_imsi,
    base_K=base_K,
    base_power_on=base_power_on,
    power_on_increment=power_on_increment,
    nof_ues=nof_ues,
    power_on_to_traffic_delay=power_on_to_traffic_delay,
    traffic_duration_sec=traffic_duration_sec,
    traffic_stop_to_dereg_delay=traffic_stop_to_dereg_delay,
    traffic_type=traffic_type,
    dereg_to_pw_off_delay=dereg_to_pw_off_delay,
    brate_dl=brate_dl,
    brate_ul=brate_ul,
    ue_start_index=ue_start_index,
)

Path(output_file).write_text(output, encoding="utf-8")
print(f"✅ {nof_ues} UEs cfg successfully written to '{output_file}'")
