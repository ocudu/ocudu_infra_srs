# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Template related utilities
"""

from pathlib import Path


def template_path(filename: str, add_ext: bool = False) -> Path:
    """
    Function to obtain the absolute path of a template file located into this directory
    :param filename
    """
    if add_ext:
        filename += ".nj"
    return Path(__file__).parent.joinpath(filename).resolve()
