# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Entrypoint to deploy cluster.
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict

import yaml

from retina.orchestrator import configs
from retina.orchestrator.const import CLUSTER_CONFIGURATION_CONFIGMAP_NAME
from retina.orchestrator.retina_kubernetes import Kubernetes
from retina.orchestrator.utils import get_current_time, validate


def _build_data(config_path: Path) -> Dict:
    with open(str(config_path), encoding="UTF-8") as file:
        conf = yaml.load(file, Loader=yaml.FullLoader)

    current_date = get_current_time()
    resource_list = base64.b64encode(json.dumps(conf["nodes"]).encode("ascii")).decode("ascii")
    cluster_resource_list = base64.b64encode(json.dumps(conf["cluster_resource_list"]).encode("ascii")).decode("ascii")

    return {
        "update-time": current_date,
        "version": conf["global"]["version"],
        "networking-mode": conf["global"]["networking-mode"],
        "dnsPolicy": conf["global"]["dnsPolicy"],
        "resource": resource_list,
        "cluster_resource_list": cluster_resource_list,
    }


def _deploy_config_map(k_server: Kubernetes, config_map_data: Dict):
    k_server.delete_config_map(CLUSTER_CONFIGURATION_CONFIGMAP_NAME)
    while k_server.config_map_exists(CLUSTER_CONFIGURATION_CONFIGMAP_NAME):
        time.sleep(1)
    k_server.create_config_map(
        configs.ConfigmapConfig(
            orch_id="retinaadmin",
            user_name="retinaadmin",
            timeout=None,
            data=config_map_data,
            name=CLUSTER_CONFIGURATION_CONFIGMAP_NAME,
        )
    )


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
        # Validate that there are no duplicate type+model combinations in cluster_resource_list
        seen = set()
        for resource in req.get("cluster_resource_list", []):
            key = (resource["type"], resource["model"])
            if key in seen:
                raise ValueError(f"Duplicate type+model combination: {key}")
            seen.add(key)

    data = _build_data(config_path=i_path)
    if dry_run:
        json.dump(data, sys.stdout)
        return

    k_server = Kubernetes(is_incluster=in_cluster)
    _deploy_config_map(k_server, data)


if __name__ == "__main__":
    main()
