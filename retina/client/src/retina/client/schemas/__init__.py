#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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
