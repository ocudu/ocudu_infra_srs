# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Schema Folder features
"""

from pathlib import Path


def schema_path(filename: str) -> str:
    """
    Function to obtain the absolute path of schemas folder
    :param filename
    """
    return str(Path(__file__).parent.joinpath(filename))
