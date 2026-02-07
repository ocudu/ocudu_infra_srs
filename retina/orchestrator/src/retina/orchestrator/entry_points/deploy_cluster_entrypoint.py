#
# Copyright 2021-2026 Software Radio Systems Limited
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
from typing import Optional

import yaml

from retina.orchestrator.reservation.utils import deploy_server
from retina.orchestrator.retina_kubernetes import Kubernetes
from retina.orchestrator.utils import validate


def _infer_runners_file(input_path: Path) -> Optional[Path]:
    """
    Infer a sibling runners file for a given cluster definition input.

    Example:
      lab_cluster.yaml -> lab_cluster_runners.yaml
      def_high_performance.yml -> def_high_performance_runners.yaml
    """
    base_dir = input_path.parent
    base_name = input_path.stem
    for suffix in ("yaml", "yml"):
        candidate = base_dir / f"{base_name}_runners.{suffix}"
        if candidate.exists():
            return candidate
    return None


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
    parser.add_argument(
        "--runners-file",
        default="",
        help="Optional runners YAML file (e.g. lab_cluster_runners.yaml). If omitted, it is inferred from --input.",
    )
    parser.add_argument("--in-cluster", action="store_true", help="Running inside a cluster.")
    parser.add_argument("--dry-run", action="store_true", help="Dry run.")
    args = parser.parse_args()
    in_cluster = args.in_cluster
    dry_run = args.dry_run

    i_path: Path = Path(args.input).resolve()
    runners_path: Optional[Path] = (
        Path(args.runners_file).resolve() if args.runners_file else _infer_runners_file(i_path)
    )

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
        # Validate that there are no duplicate type+model combinations in cluster_resource_list
        seen = set()
        for resource in req.get("cluster_resource_list", []):
            key = (resource["type"], resource["model"])
            if key in seen:
                raise ValueError(f"Duplicate type+model combination: {key}")
            seen.add(key)

    if not dry_run:
        k_server = Kubernetes(is_incluster=in_cluster)
        deploy_server(config_path=i_path, k_server=k_server, runners_path=runners_path)


if __name__ == "__main__":
    main()
