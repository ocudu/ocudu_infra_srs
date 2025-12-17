#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Entrypoint to deploy cluster.
"""

import argparse
import json
import os
from pathlib import Path

import yaml

from retina.orchestrator.reservation.utils import deploy_server
from retina.orchestrator.srs_kubernetes import Kubernetes
from retina.orchestrator.utils import validate


def main():
    """
    Entrypoint for deploy cluster
    """
    parser = argparse.ArgumentParser(description="Deploy cluster.")
    parser.add_argument(
        "--input",
        default="../../../../tests/helpers/cluster.yml",
        help="YAML file with the resources.",
    )
    parser.add_argument("--in-cluster", action="store_true", help="Running inside a cluster.")
    parser.add_argument("--dry-run", action="store_true", help="Dry run.")
    args = parser.parse_args()
    in_cluster = args.in_cluster
    dry_run = args.dry_run

    i_path: Path = Path(args.input).resolve()

    # Validate input yaml with jsonschema
    with open(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "cluster_schema.json"),
        "r",
        encoding="utf-8",
    ) as file_descriptor:
        testbed_schema = json.load(file_descriptor)

        with open(i_path, encoding="UTF8") as file:
            target_content = file.read()

        req = yaml.load(target_content, Loader=yaml.FullLoader)
        validate(req, testbed_schema)

    if not dry_run:
        k_server = Kubernetes(is_incluster=in_cluster)
        deploy_server(config_path=i_path, k_server=k_server)


if __name__ == "__main__":
    main()
