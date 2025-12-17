#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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
