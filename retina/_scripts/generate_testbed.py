# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Generate a testbed.yml file from docker-compose.yml.
"""

import argparse
from pathlib import Path

import yaml


def load_yaml(file_path):
    """
    Load a YAML file and return its contents.
    """
    with open(file_path, encoding="utf-8") as file:
        return yaml.safe_load(file)


def main():
    """
    Main function to parse arguments and generate .env file.
    """

    parser = argparse.ArgumentParser(description="Testbed generator from docker compose tool")
    parser.add_argument("--profile", required=True, help="docker compose profile")
    args = parser.parse_args()

    current_dir = Path.cwd()
    compose_data = load_yaml(current_dir / "docker-compose.yml")
    output_file = current_dir / "testbed.yml"

    service_info = []
    for service_name, service_config in compose_data.get("services", {}).items():
        if service_name == "launcher":
            continue

        if args.profile in service_config.get("profiles", []):

            # Get IP address
            ip_address = ""
            for network_dict in service_config.get("networks", {}).values():
                ip_address = network_dict.get("ipv4_address")
                if ip_address:
                    break
            if not ip_address:
                continue

            # Get ports and type
            retina_ports = [50051]  # Default Agent port
            for env_var, value in service_config.get("environment", {}).items():
                if env_var == "RETINA_PORTS":
                    retina_ports = [int(p) for p in value.split(" ")]
                    break

            # Create entry
            for idx, port in enumerate(retina_ports):
                service_info.append(
                    {
                        "name": service_name + "-" + str(idx + 1),
                        "address": ip_address,
                        "port": port,
                        **service_config.get("x-testbed", {}),
                    }
                )

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump({"id": "local", "node_list": service_info}, f, sort_keys=False)


if __name__ == "__main__":
    main()
