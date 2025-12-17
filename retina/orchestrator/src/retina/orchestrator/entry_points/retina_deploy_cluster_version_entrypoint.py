#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Update retina version entrypoint
"""

import argparse
import logging
import re
import sys

from retina.orchestrator.cluster_utils import get_retina_version, set_retina_version
from retina.orchestrator.entry_points.utils import set_default_colored_logger
from retina.orchestrator.srs_kubernetes import Kubernetes


def parse_version(version):
    """
    Parse version
    """
    major, minor, patch = map(int, version.split("."))
    return major, minor, patch


def is_greater_version(version1, version2):
    """
    Check if version1 is greater than version2
    """
    major1, minor1, patch1 = parse_version(version1)
    major2, minor2, patch2 = parse_version(version2)

    if major1 > major2:
        return True
    if major1 < major2:
        return False

    if minor1 > minor2:
        return True
    if minor1 < minor2:
        return False

    return patch1 > patch2


def is_strict_semver(version):
    """
    Check if version is a strict semantic version
    """
    strict_semver_pattern = r"^\d+\.\d+\.\d+$"
    return re.match(strict_semver_pattern, version) is not None


def main():
    """
    Main
    """
    set_default_colored_logger()

    parser = argparse.ArgumentParser(description="Set Retina version in the cluster.")
    parser.add_argument("--version", default="10.0.0", help="Retina version to set.", type=str)
    parser.add_argument("--in-cluster", action="store_true", help="Running inside a cluster.")

    args = parser.parse_args()
    new_version = args.version
    in_cluster = args.in_cluster

    k_server = Kubernetes(is_incluster=in_cluster)

    old_version = get_retina_version(k_server)

    logging.info("Current Retina version: %s", old_version)
    logging.info("New version: %s", new_version)

    # Check if the version is a strict semantic version
    if not is_strict_semver(new_version):
        logging.error("Invalid version. The version must be a strict semantic version.")
        sys.exit(1)

    # Check if new version is major than the old version with semantic version
    if old_version and not is_greater_version(new_version, old_version):
        logging.error("Invalid version. The new version must be greater than the old version.")
        sys.exit(1)

    set_retina_version(k_server, new_version)

    new_old_version = get_retina_version(k_server)
    if new_old_version != new_version:
        logging.error("Error setting the version.")
        sys.exit(1)
    else:
        logging.info("Version set successfully.")


if __name__ == "__main__":
    main()
