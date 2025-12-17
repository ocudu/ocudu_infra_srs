#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Entry points utils
"""

import logging
import sys
from typing import Iterable

from rich.console import Console
from rich.table import Table

from retina.orchestrator.orchestration_network import SRSPod

GITLAB_RUNNER_POD_PREFIX = "glr-ci"
GITLAB_RUNNER_NAMESPACE = "gitlab-runner"


RESET_COLOR = "\033[0m"
LEVEL_COLORS = {
    logging.DEBUG: "\x1b[34;20m",
    logging.INFO: "\x1b[32;20m",
    logging.WARNING: "\x1b[33;20m",
    logging.ERROR: "\x1b[31;20m",
    logging.CRITICAL: "\x1b[35;20m",
}


class CustomFormatter(logging.Formatter):
    """
    Custom formatter
    """

    def format(self, record):
        """
        Format record
        """
        level_color = LEVEL_COLORS.get(record.levelno, RESET_COLOR)

        record.levelname = f"{level_color}[{record.levelname}]{RESET_COLOR}"

        format_string = "%(asctime)s %(levelname)s %(message)s"
        formatter = logging.Formatter(format_string)
        return formatter.format(record)


def set_default_colored_logger(log_level=logging.INFO):
    """
    Set default colored logger
    """
    logger = logging.getLogger()

    if not logger.hasHandlers():
        logger.setLevel(log_level)  # Nivel por defecto
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(CustomFormatter())
        logger.addHandler(console_handler)


def check_user_name(user_name: str):
    """
    Get user name
    """
    forbidden_username = ["root", "admin", "administrator", "sysadmin", "system", "superuser", "su", "sudo", "srsadmin"]
    if user_name in forbidden_username:
        logging.error(
            "Forbidden username: %s. Please choose another one not in the list %s", user_name, forbidden_username
        )
        sys.exit(1)


def print_table(pod_list: Iterable[SRSPod]):
    """
    Print resource table
    """
    table = Table(title="Infrastructure")

    table.add_column("Name", justify="right", style="cyan")
    table.add_column("IP", style="magenta")
    table.add_column("Port", style="magenta")
    table.add_column("Pod name", style="magenta")
    table.add_column("Internal Pod IP", style="magenta")
    table.add_column("Node", style="magenta")

    for pod in pod_list:
        name = pod.name
        address = pod.address
        port = "/".join(map(str, pod.port_array))
        pod_name = str(pod.pod_name)
        pod_ip = str(pod.pod_ip)
        node_name = pod.node_name
        table.add_row(name, address, port, pod_name, pod_ip, node_name)

    console = Console()
    console.print(table)


def print_table_resources(pod_list: Iterable[SRSPod]):
    """
    Print resource table
    """
    table = Table(title="Resources")
    table.add_column("ID name", justify="right", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("IP", style="magenta")
    table.add_column("Args", style="magenta")
    table.add_column("RS", style="magenta")

    print_table_ok = False
    for pod in pod_list:
        for resource in pod.resource.get_resources():
            if not resource.is_zmq_resource():
                id_name = resource.id_name
                model = resource.model if hasattr(resource, "id_name") else ""
                ip_address = resource.ip_address if hasattr(resource, "ip_address") else ""
                args = resource.args if hasattr(resource, "args") else ""
                space = str(resource.space) if hasattr(resource, "space") else "None"

                table.add_row(id_name, model, ip_address, args, space)
                print_table_ok = True

    if print_table_ok:
        console = Console()
        console.print(table)


def get_error_level(input_loglevel: str) -> int:
    """
    Get error level
    """
    log_level = logging.ERROR
    if input_loglevel == "info":
        log_level = logging.INFO
    elif input_loglevel == "debug":
        log_level = logging.DEBUG
    elif input_loglevel == "error":
        log_level = logging.ERROR
    elif input_loglevel == "warning":
        log_level = logging.WARNING
    return log_level
