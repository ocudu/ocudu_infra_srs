#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Entrypoint request validator.
"""

import argparse
import os

from retina.orchestrator.utils import parse_request


def main():
    """
    Entrypoint to resource cluster reservation.
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
