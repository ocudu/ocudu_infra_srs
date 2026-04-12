# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Utils
"""

import getpass
import json
import logging
import os
import random
import shutil
import socket
import string
import subprocess
import tempfile
from concurrent.futures import as_completed, ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import yaml
from dotenv import dotenv_values
from jsonschema import validate

from retina.orchestrator import const


def get_retina_user():
    """
    Get current user name
    """
    user_name = getpass.getuser()
    if user_name == "":
        user_name = "codebot"
    return user_name.lower()


def run_command(command: str, timeout: int = 30 * 60):
    """
    Exec command
    """
    try:
        result = subprocess.run(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=timeout
        )
        return result.stdout.decode("utf-8")
    except subprocess.CalledProcessError as err:
        logging.error(err.stdout.decode("utf-8"))
        raise err from None


def get_ssh_key():
    """
    Get ssh hey

    :return: public key
    """
    homedir = os.path.expanduser("~")
    ssh_path = os.path.join(homedir, ".ssh", "id_rsa.pub")
    with open(ssh_path, encoding="UTF-8") as file:
        ssh_key = file.read()
    return ssh_key


def get_random_string():
    """
    Get random string

    :return: random string
    """
    length = 10
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    return result_str


def get_current_time():
    """
    Get current datatime
    """
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def get_pod_name(basename, orchid):
    """
    Get pod name
    """
    return f"{basename}-{orchid}"


def get_port_configmap_name(port_number):
    """
    Get configmap name
    """
    return f"{const.ELEMENT_PREFIX}-{port_number}-configmap-port"


def get_orchid_configmap_name():
    """
    Get configmap name
    """
    orch_id = get_random_string()
    return orch_id, get_orchid_configmap_name_from_id(orch_id)


def get_orchid_configmap_name_from_id(orch_id: str):
    """
    Get configmap name
    """
    return f"{const.ELEMENT_PREFIX}-{orch_id}-configmap-orchid"


def get_specific_labels(config, key):
    """
    Get label specific
    """
    labels = []
    if key in config:
        labels = config[key]
    return labels


def get_value_from_dict(key: str, conf):
    """
    Get value fron dict
    """
    if key in conf:
        return conf[key]
    return None


MAX_NAME_SIZE = 23


def parse_request(request_path: str, max_name_size=MAX_NAME_SIZE) -> List[Dict]:
    """
    Check if the request yaml is valid
    """

    with open(request_path, encoding="UTF8") as file:
        target_content = file.read()

    # Read variables in .env files in same folder as request
    env_variables = {}
    for file_path in Path(request_path).parent.glob("*.env"):
        env_variables.update(dotenv_values(file_path))

    # Substitute variables
    for key, value in env_variables.items():
        if value is not None:
            target_content = target_content.replace(f"${{{key}}}", value)

    req = yaml.load(target_content, Loader=yaml.FullLoader)

    # Check the request
    with open(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "request_schema.json"),
        "r",
        encoding="utf-8",
    ) as file_descriptor:
        request_schema = json.load(file_descriptor)

        validate(req, request_schema)

    # Check name size
    for req_inst in req:
        if len(req_inst["name"]) > max_name_size:
            raise RuntimeError(f"Name {req_inst['name']} is too long. Max size is {max_name_size} chars.")

    return req


def check_binary_can_exec(binary_path: str):
    """
    Check if binary has execution permissions
    """
    if not os.access(binary_path, os.X_OK):
        raise RuntimeError(f"{binary_path} hasn't execution permissions.")


def check_port_list(ip_add: str, port_list: Tuple) -> bool:
    """
    Check if all ports in the port list are open using parallel execution.
    """
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(check_port, ip_add, port) for port in port_list]

        for future in as_completed(futures):
            if not future.result():
                return False
    return True


def check_port(ip_add: str, port: int) -> bool:
    """
    Check if port is open
    """
    for socket_type in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
        with socket.socket(socket.AF_INET, socket_type) as sock:
            with suppress(Exception):
                sock.connect((ip_add, port))
                return True
    return False


def validate_manifest(manifest: Dict) -> bool:
    """
    Validate manifest
    """
    is_valid = True
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as temp_file:
        yaml.dump(manifest, temp_file, default_flow_style=False)
        temp_file_path = temp_file.name

    try:
        binary_name = "kubeval"
        find_in_path(binary_name)
        output = run_command(f"{binary_name} --strict --ignore-missing-schemas {temp_file_path}")

    except FileNotFoundError:
        is_valid = True
    except subprocess.CalledProcessError as err:
        output = err.stdout.decode("utf-8").lower()
        if "failed initializing schema" not in output and "PASS" not in output:
            is_valid = False
    finally:
        os.remove(temp_file_path)
    return is_valid


def get_kubeconfig_extra_list() -> List[str]:
    """
    Get kubeconfig extra list
    """
    paths_str = os.getenv("KUBECONFIG_EXTRA")

    if paths_str is not None:
        paths_list = paths_str.split(";")
        return paths_list
    return []


def find_in_path(binary_name: str) -> str:
    """
    Find binary in path
    """
    if Path(binary_name).is_absolute() and Path(binary_name).exists():
        return binary_name
    path = shutil.which(binary_name)
    if path is None:
        raise FileNotFoundError(f"Can not found '{binary_name}' in path")
    return path
