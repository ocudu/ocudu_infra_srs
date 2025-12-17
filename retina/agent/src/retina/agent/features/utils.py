#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Utils
"""

import inspect


def get_module_variables(module):
    """
    Get all variables from a module
    """
    variables = {}
    for name, value in inspect.getmembers(module):
        if name.startswith("__"):
            continue
        if inspect.isfunction(value) or inspect.isclass(value):
            continue
        variables[name] = value
    return variables
