# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Module with a set of parameters related with gnb configuration
They must be lowercase and snake case because they're variables and not constants
Must always be explicit typed.
"""

from typing import List, TypedDict, Union

from retina.agent.app.parameter_manager import convert_to_parameter_source, ParameterNamespace

convert_to_parameter_source(__name__, ParameterNamespace.GNB)
convert_to_parameter_source(__name__, ParameterNamespace.CU)
convert_to_parameter_source(__name__, ParameterNamespace.CU_CP)
convert_to_parameter_source(__name__, ParameterNamespace.CU_UP)
convert_to_parameter_source(__name__, ParameterNamespace.CU)
convert_to_parameter_source(__name__, ParameterNamespace.DU)


##########
# Params #
##########
# pylint: disable=invalid-name
gnb_id: int = 411
gnb_id_bit_length: int = 22
gnb_du_id: int = 0
log_level: str = "info"
enable_high_latency_diagnostics: bool = False
tx_gain: float = -1  # Default value in testbed
rx_gain: float = -1  # Default value in testbed
common_scs: int = 15
sample_rate: int = -1  # Default value in testbed
band: int = 7
bandwidth: int = 20
dl_arfcn: int = 536020
tac: int = 7
pci: int = 1
sector_id: int = 0
prach_root_sequence_index: int = 0
mcs: int = -1
pdsch_mcs_table: str = ""
pusch_mcs_table: str = ""
pcap: bool = True
mac_enable: bool = False
mac_filename: str = "mac.pcap"
rlc_enable: bool = False
rlc_rb_type: str = "srb"
rlc_filename: str = "rlc.pcap"
rlc_metrics: bool = False
ngap_filename: str = "ngap.pcap"
e1ap_filename: str = "e1ap.pcap"
f1ap_filename: str = "f1ap.pcap"
n3_enable: bool = False
n3_filename: str = "n3.pcap"
e2_du_enable: bool = False
e2ap_du_filename: str = "e2ap_du.pcap"
metrics_filename_json: str = "metrics.json"
metrics_hostname: str = ""
metrics_port: int = 0
time_alignment_calibration: Union[int, str] = "auto"
common_search_space_enable: bool = False
prach_config_index: int = -1
max_rb_size: int = -1
enable_channel_noise: bool = False
max_pdschs_per_slot: int = -1
max_puschs_per_slot: int = -1
enable_qos_um: bool = False
enable_qos_viavi: bool = False
enable_qos_reestablishment: bool = False
num_cells: int = 1
cell_offset: int = 0
nof_antennas_dl: int = 1
nof_antennas_ul: int = 1
warn_on_drop: bool = False
enable_integrity_protection: bool = False
enable_security_mode: bool = False
enable_dddsu: bool = False
warning_allowlist: List[str] = []
enable_drx: bool = False
cu_cp_inactivity_timer: int = -1
pucch_formats: str = "f1_and_f2"
request_pdu_session_timeout: int = -1
rrc_procedure_guard_time_ms: int = -1
ta_target: float = 0
ta_meas_slot_prohibit_period: int = -1
ta_meas_slot_period: int = -1
ta_cmd_offset_threshold: int = -1
pdsch_interleaving_bundle_size: int = 0


class SliceInfo(TypedDict, total=False):
    """
    Dictionary to store Slice parameters.
    """

    sd: int
    min_prb_policy_ratio: int
    max_prb_policy_ratio: int


slices: list[SliceInfo] = []


# NTN
class Sib19Params(TypedDict, total=False):  # total=False makes keys optional
    """
    Dictionary to store SIB19 parameters.
    """

    ntn_ul_sync_validity_dur: int
    cell_specific_koffset: int
    ta_common: float
    ta_common_drift: float
    ta_common_drift_variant: float
    use_ephemeris_orbital: bool
    semi_major_axis: float
    eccentricity: float
    periapsis: float
    longitude: float
    inclination: float
    mean_anomaly: float
    pos_x: float
    pos_y: float
    pos_z: float
    vel_x: float
    vel_y: float
    vel_z: float


ntn_enable: bool = False
sib19: Sib19Params = {}
time_multiplier: float = 0
