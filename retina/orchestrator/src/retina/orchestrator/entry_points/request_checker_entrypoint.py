# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Entrypoint request validator.
"""

import argparse
import os

from retina.orchestrator.utils import parse_request


def main():
    """
    Entrypoint to validate retina requests
    """
    parser = argparse.ArgumentParser(description="Retina request YAML validator.")
    parser.add_argument("--input", help="File path to validate.")

    args = parser.parse_args()

    current_directory = os.getcwd()
    input_arg = os.path.join(current_directory, args.input)

    pre = "*********************************************************************************"
    print(f"{pre}\nValidating request {input_arg}\n{pre}")

    parse_request(input_arg)
    print("OK")


if __name__ == "__main__":
    main()
