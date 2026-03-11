#!/usr/bin/env python3

# Generate UE configuration blocks with incremental IMSI, K, and start times

# Generate UE configuration blocks with incremental IMSI, K, and start times

# ==== Configuration ====
output_file = "ue_list_512.cfg"   # File where blocks will be written
base_imsi = int("1010123456789",10)     # Starting IMSI (from the previous block)
base_K = int("00112233445566778899aabbccddeeff", 16)
base_power_on = 0           # Time at which first UE is powered on
base_ext_app = 1            # Possibly not used
power_on_increment = 0.1    # Time diff (to prev UE) at which next UE is powered on
ext_app_increment = 2       # Time diff (to prev UE) at which next UE starts traffic
nof_ues = 512               # Total number of UEs to generate
ues_per_block = 1           # Num of UEs attaching simultaneously NOTE: ONLY TESTED with ues_per_block = 1
traffic_duration_sec = 180 # Duration of traffic in seconds
brate_dl = 800000          # Bitrate of CBR traffic in bps
brate_ul = 350000          # Bitrate of CBR traffic in bps

num_blocks = (int)(nof_ues / ues_per_block)           # how many groups to generate
ue_start_index = 1      # first UE index in first new block
# ========================

with open(output_file, "w") as f:
    initial_block = f"""
  ue_list: [
"""
    f.write(initial_block)

    for i in range(num_blocks):
        ue_first = ue_start_index + i * ues_per_block
        ue_last = ue_first + ues_per_block - 1
        imsi = base_imsi + i * ues_per_block
        K_hex = format(base_K + i * ues_per_block, "032x")
        power_on = base_power_on + i * power_on_increment
        #ext_app = base_ext_app + i * ext_app_increment
        cbr_start = base_power_on + nof_ues * power_on_increment + 10
        cbr_stop = cbr_start + traffic_duration_sec
        dereg_time = cbr_stop + 20 + i * power_on_increment
        power_off = dereg_time + 5
        quit_time = power_off + 5
        quit_event = f"        {{\n          event: \"quit\",\n          start_time: {quit_time},\n        }},\n" if i == num_blocks - 1 else ""

        block = f"""    /* UEs idx [{ue_first}, {ue_last}]*/
    {{
      sim_algo: "xor",
      imsi: "00{imsi}",
      K: "{K_hex}",
      apn: "srsapn",
      as_release: 15,
      ue_category: "nr",
      power_control_enabled: false,
      position: [100, 0], 
      speed: 0,
      channel: {{
        type: "awgn",
      }},

      attach_pdn_type: "ipv4",
      ue_count: {ues_per_block},
      sim_events: [
        {{
          event: "power_on",
          start_time: {power_on},
        }},
        {{
            start_time: {cbr_start},
            end_time: {cbr_stop},
            dst_addr: "192.168.3.1",
            payload_len: 1400,
            bit_rate: {brate_dl},
            event: "cbr_recv"
        }},
        {{
            start_time: {cbr_start},
            end_time: {cbr_stop},
            dst_addr: "192.168.3.1",
            payload_len: 1400,
            bit_rate: {brate_ul},
            event: "cbr_send"
        }},
        {{
          event: "deregister",
          start_time: {dereg_time},
        }},
        {{
          event: "power_off",
          start_time: {power_off},
        }},
{quit_event}      ]
    }},"""

        f.write(block)
    closing_block = f""" 
  ]
"""
    f.write(closing_block)
print(f"✅ {num_blocks} UE blocks successfully written to '{output_file}'")        