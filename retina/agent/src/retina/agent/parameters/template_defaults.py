#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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
cu: str = ""
du: str = ""
ru: str = ""
qos: str = ""
ims: str = ""
