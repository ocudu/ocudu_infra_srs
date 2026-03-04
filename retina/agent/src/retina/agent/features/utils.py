# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

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
