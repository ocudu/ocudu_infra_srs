# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Module with a set of parameters related with template configuration
They must be lowercase and snake case because they're variables and not constants
Must always be explicit typed.
"""

from retina.agent.app.parameter_manager import convert_to_parameter_source, ParameterNamespace

convert_to_parameter_source(__name__, ParameterNamespace.TEMPLATE)

##########
# Params #
##########
# pylint: disable=invalid-name
main: str = ""
ue: str = ""
cu: str = ""
du: str = ""
ru: str = ""
qos: str = ""
core: str = ""
ims: str = ""
