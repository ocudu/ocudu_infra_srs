# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Utilities for checking Amarisoft license status.

This module integrates with the lisenses.py script in the parent directory
to provide functions for checking license availability and status.
"""

import logging
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table

from retina.orchestrator.license_utils.licenses import LicenseClient
from retina.orchestrator.orchestration_network import Kubernetes
from retina.orchestrator.reservation.managers import get_resources_in_cluster
from retina.orchestrator.reservation.resources import ResourceLicense
from retina.orchestrator.reservation.transformations import get_cluster_resources


def get_license_client(k_server: Kubernetes) -> LicenseClient:
    """
    Create and return a configured LicenseClient instance.

    Args:
        host: IP or hostname of the License Server
        port: Remote API port (default 9006)
        password: Password if config uses com_auth
        use_ssl: True for wss:// (TLS), False for ws://

    Returns:
        Configured LicenseClient instance
    """
    for resource in get_cluster_resources(get_resources_in_cluster(k_server)).get_resources():
        if isinstance(resource, ResourceLicense) and resource.model.startswith("amarisoft"):
            return LicenseClient(host=resource.ip_address or "", port=9006, password=None, use_ssl=False)
    raise RuntimeError("Amarisoft License Server not found in the cluster")


def get_license_status(k_server: Kubernetes) -> Dict:
    """
    Get the full license status from the Amari license server.

    Returns:
        Dictionary containing license information
    """
    try:
        client = get_license_client(k_server)
        license_info = client.list_licenses()
        logging.info("License info: %s", license_info)
        return license_info
    except (OSError, RuntimeError) as e:
        logging.error("Error getting license status: %s", e)
        return {"error": str(e)}


def get_available_licenses(k_server: Kubernetes) -> List[Dict]:
    """
    Get list of available (not in use) licenses.

    Returns:
        List of available license dictionaries
    """
    try:
        license_info = get_license_status(k_server)
        if "error" in license_info:
            return []

        available_licenses = []
        for license_entry in license_info.get("licenses", []):
            if not license_entry.get("in_use", False):
                available_licenses.append(license_entry)

        return available_licenses
    except (OSError, RuntimeError) as e:
        logging.error("Error getting available licenses:  %s", e)
        return []


def get_used_licenses(k_server: Kubernetes) -> List[Dict]:
    """
    Get list of licenses currently in use.

    Returns:
        List of in-use license dictionaries
    """
    try:
        license_info = get_license_status(k_server)
        if "error" in license_info:
            return []

        used_licenses = []
        available_licenses = []
        for license_entry in license_info.get("licenses", []):
            if is_license_in_use(license_entry):
                used_licenses.append(license_entry)
            else:
                available_licenses.append(license_entry)

        return used_licenses
    except (OSError, RuntimeError) as e:
        logging.error("Error getting used licenses:  %s", e)
        return []


def check_license_availability(k_server: Kubernetes, license_type: Optional[str] = None) -> bool:
    """
    Check if there are any available licenses of the specified type.
    If no type is specified, checks if any licenses are available.

    Args:
        license_type: Optional type of license to check for

    Returns:
        True if licenses are available, False otherwise
    """
    available_licenses = get_available_licenses(k_server)

    if not license_type:
        return len(available_licenses) > 0

    for license_entry in available_licenses:
        if license_entry.get("type", "").lower() == license_type.lower():
            return True
    return False


# pylint: disable=missing-function-docstring
def is_license_in_use(license_entry):
    origin = license_entry.get("origin", "")
    if "from" in origin:
        return True
    connections = license_entry.get("connections", [])
    if connections:
        return True
    return False


# pylint: disable=too-many-locals
def display_license_info(k_server: Kubernetes, verbose: bool = False) -> None:
    """
    Display license information in a rich table format.

    Args:
        verbose: If True, shows additional license details
    """
    try:
        client = get_license_client(k_server)
        license_info = client.list_licenses()
        license_list = license_info.get("licenses", [])

        table_title = "License Information" if not verbose else "License Details"
        table = Table(title=table_title)

        table.add_column("License ID", style="cyan", no_wrap=True)
        table.add_column("Status", style="red")
        table.add_column("Tag", style="magenta")
        table.add_column("Products", style="blue")
        if verbose:
            table.add_column("Version", style="white")
            table.add_column("Max", style="white")
            table.add_column("Origin", style="green")

        for lic in license_list:
            uid = lic.get("uid", "N/A")
            tag = lic.get("tag", "")
            products = lic.get("products", "N/A")
            origin = lic.get("origin", "")
            status = "In Use" if is_license_in_use(lic) else "Available"
            if verbose:
                version = lic.get("version", "N/A")
                max_conn = str(lic.get("max", "N/A"))
                table.add_row(uid, status, tag, products, version, max_conn, origin)
            else:
                table.add_row(uid, status, tag, products)

        console = Console()
        console.print(table)

        if not license_list:
            print("No licenses found.")

    except (OSError, RuntimeError) as e:
        logging.error("Error displaying license information:  %s", e)
