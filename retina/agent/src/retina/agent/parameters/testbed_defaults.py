#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Module with a set of parameters related with testbed configuration
They must be lowercase and snake case because they're variables and not constants
Must always be explicit typed.
"""

from typing import List

from retina.agent.app.parameter_manager import convert_to_parameter_source, ParameterNamespace

convert_to_parameter_source(__name__, ParameterNamespace.TESTBED)

##########
# Params #
##########
# pylint: disable=invalid-name
type: str = "zmq"  # zmq, sdr, ru, android, accelerator # pylint:disable=redefined-builtin
# Amarisoft License
license_server: str = ""
license_args: str = ""
# ZMQ
ip: str = ""
ip_zmq: str = ""
port_array: List[int] = list(range(31000, 31008))
f1u_port: int = 2153
# SDR
model: str = ""
args: str = ""  # hw args
sync: str = "none"  # hw sync
# RU
ru_network_interface: List[str] = []
ru_du_mac_addr: List[str] = []
ru_ru_mac_addr: List[str] = []
ru_vlan_tag_up: List[str] = []
ru_vlan_tag_cp: List[str] = []
ru_prach_port_id: str = ""
ru_dl_port_id: str = ""
ru_ul_port_id: str = ""
# COTS identifier and uSIM params
serial_id: str = ""
imsi: str = "001010123456789"
k: str = "00112233445566778899aabbccddeeff"
opc: str = "63bfa50ee6523365ff14c1f45f88737d"
amf: str = "8000"
tel: int = 9876543201
sd: str = ""
sim_algo: str = "milenage"
adb_key: str = ""
# Emulator
user: str = ""
password: str = ""
api_address: str = "127.0.0.1"
api_port: int = 9002
tma_path: str = ""
amf_address: str = ""
amf_port: int = 38412
# Accelerator
accelerator_model: str = ""
accelerator_type: str = ""
accelerator_hwacc_type: str = ""
accelerator_id: int = 0
accelerator_cb_mode: bool = False
accelerator_pdsch_enc_nof_hwacc: int = 0
accelerator_pusch_dec_nof_hwacc: int = 0
accelerator_harq_context_size: int = 0
accelerator_extra_eal_args: str = ""
# All
sample_rate: int = 61440000
tx_gain: float = 0
rx_gain: float = 0
# CPU isolation
lcores_eal_args: str = ""
