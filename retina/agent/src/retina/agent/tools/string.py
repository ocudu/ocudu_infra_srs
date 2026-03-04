# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
String manipulation tools
"""

import re

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def remove_ansi_escapes(my_string: str) -> str:
    """
    Remove ANSI escape syntax from a string
    """
    return ANSI_ESCAPE.sub("", my_string)
