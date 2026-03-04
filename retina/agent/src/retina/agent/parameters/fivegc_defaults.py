# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Module with a set of parameters related with amarisoft ue configuration
They must be lowercase and snake case because they're variables and not constants
Must always be explicit typed.
"""

from typing import List

from retina.agent.app.parameter_manager import convert_to_parameter_source, ParameterNamespace

convert_to_parameter_source(__name__, ParameterNamespace.FIVEGC)

##########
# Params #
##########
# pylint: disable=invalid-name
log_level: str = "info"
db_addr: str = "127.0.0.1:27017"
bin_prefix: str = "/usr/local"
udr_ip: str = "127.0.0.20"
udr_port: int = 7777
tun_subnet: str = "10.45.0.1"
tun_mask: int = 16
apn: str = "srsapn"
ims_mode: str = ""  # enabled, not_registering
slices: List[int] = []
