# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Module with a set of parameters related with ue configuration
They must be lowercase and snake case because they're variables and not constants
Must always be explicit typed.
"""

from typing import List, Tuple, TypedDict

from retina.agent.app.parameter_manager import convert_to_parameter_source, ParameterNamespace
from retina.agent.templates import template_path

convert_to_parameter_source(__name__, ParameterNamespace.UE)

##########
# Params #
##########
# pylint: disable=invalid-name
# Logging
log_level: str = "info"
log_ip_level: str = ""
log_s72_level: str = ""
log_com_level: str = ""
log_prod_level: str = ""
log_phy_level: str = ""
mac_filename: str = "mac.pcap"
mac_nr_filename: str = "mac_nr.pcap"
nas_filename: str = "ue_nas.pcap"
metrics_filename_csv: str = "metrics.csv"
metrics_filename_json: str = "metrics.json"

# RF driver
tx_gain: float = -1  # Default value in testbed
rx_gain: float = -1  # Default value in testbed
rx_ant: str = ""
freq_offset: int = 0
time_adv_nsamples: int = 0

# Cell
nof_antennas_dl: int = 1
nof_antennas_ul: int = 1
rx_to_tx_latency: int = -1
num_cells: int = 1
ul_noise_spd: int = 0
noise_spd: int = 0
sample_rate: int = -1  # Default value in testbed
global_timing_advance: int = -1
nb_threads: int = -1
n_rb_dl: int = 0
cell_position_offset: Tuple[float, float, float] = (1000, 0, 0)
pdcch_log: bool = False
pdcch_decode_opt_threshold: float = 0
ue_sds: List[str] = []

# UE
apn: str = "internet"
tun_sh_path: str = template_path("amarisoft_ue_tun.sh")
quit_on_start: bool = False

# NTN
ntn_enable: bool = False
latitude: float = 0
longitude: float = 0
altitude: float = 0

# temporal
ue_simulator_mode: bool = False


# pylint: disable=duplicate-code
class CellBandArray(TypedDict, total=False):
    """
    Dictionary to store Cell parameters.
    """

    band: int
    bandwidth: int
    dl_nr_arfcn: int
    ssb_nr_arfcn: int
    subcarrier_spacing: int
    ssb_subcarrier_spacing: int


cells: list[CellBandArray] = []
