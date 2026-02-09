#!/usr/bin/env python3
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Synchronizes Amarisoft license usage with Retina reservations.

This script ensures that active licenses reported by the Amarisoft license server
are properly reflected in Retina's reservation system by:

1. Checking if active licenses have corresponding Retina reservations under the
    "amarisoft" user with matching tags
2. For licenses without proper reservations, attempting to reserve them or
    reassigning existing reservations from other users
3. Releasing unused licenses that are still reserved under the "amarisoft" user
"""

import argparse
import logging
from dataclasses import dataclass
from typing import List

from retina.orchestrator.entry_points.resource_utils import release_cluster_resource, reserve_cluster_resource
from retina.orchestrator.license_utils.license_utils import get_used_licenses
from retina.orchestrator.reservation.managers import get_resources_in_cluster
from retina.orchestrator.reservation.resources import ClusterResource
from retina.orchestrator.reservation.transformations import get_cluster_resources
from retina.orchestrator.retina_kubernetes import Kubernetes

FAKE_USER = "amarisoft"


@dataclass
class _License:
    name: str
    tag: str
    username: str

    def __repr__(self):
        return f"{self.name} (tag={self.tag}, user={self.username})"


def main():
    """
    Main function
    """
    logging.basicConfig(
        format="%(asctime)s \x1b[32;20m[%(levelname)s]\x1b[0m %(message)s",
        level=logging.INFO,
    )

    parser = argparse.ArgumentParser(description="Enable disable Gitlab runners.")
    parser.add_argument("--incluster", action="store_true", help="Running inside the cluster")
    args = parser.parse_args()

    k_server = Kubernetes(is_incluster=args.incluster)
    _sync_license_reservations(k_server)


# pylint: disable=too-many-branches
def _sync_license_reservations(k_server: Kubernetes):
    """
    Sync Amarisoft license reservations with retina
    """
    reserved_server_licenses = []
    for ul in get_used_licenses(k_server):
        tag = ul.get("tag")
        if not tag:
            logging.warning(
                "[ ! ] Skipping Amarisoft license without tag (uid=%s)",
                ul.get("uid"),
            )
            continue

        reserved_server_licenses.append(
            _License(
                name=ul["uid"],
                tag=tag,
                username=FAKE_USER,
            )
        )

    all_retina_licenses: List[_License] = []
    for resource in get_cluster_resources(get_resources_in_cluster(k_server)).get_resources():
        if resource.model.startswith("amarisoft"):
            all_retina_licenses.append(
                _License(
                    name=resource.get_full_name(),
                    tag=resource.args,
                    username=_get_resource_username(resource, k_server),
                )
            )
    all_retina_licenses = list(sorted(all_retina_licenses, key=lambda x: (x.username != FAKE_USER, not x.username, x.tag)))
    logging.info("Retina info: %s", all_retina_licenses)

    # Match already reserved licenses
    for server_license in list(reserved_server_licenses):
        for retina_license in all_retina_licenses:
            if retina_license.tag == server_license.tag:
                # 1 - Check if the license is already reserved by the same user
                if server_license.username == retina_license.username:
                    all_retina_licenses.remove(retina_license)
                    reserved_server_licenses.remove(server_license)
                    logging.info(
                        "[ | ] License '%s' is already reserved in retina: '%s'", server_license, retina_license
                    )
                    break
                # 2 - Check if the license is already reserved by another user
                if retina_license.username and server_license.username != retina_license.username:
                    all_retina_licenses.remove(retina_license)
                    reserved_server_licenses.remove(server_license)
                    logging.info(
                        "[ | ] License '%s' is already reserved in retina: '%s'", server_license, retina_license
                    )
                    break

    # Reserve the license for the user
    for server_license in reserved_server_licenses:
        for retina_license in all_retina_licenses:
            if retina_license.tag == server_license.tag and not retina_license.username:
                logging.info("[ + ] Reserving license '%s' using '%s'", server_license, retina_license)
                reserve_cluster_resource(k_server, FAKE_USER, retina_license.name, timeout=20)
                all_retina_licenses.remove(retina_license)
                break

    # Free licenses in retina that are not used in server
    for retina_license in all_retina_licenses:
        if retina_license.username == FAKE_USER:
            logging.info("[ - ] Releasing license '%s' reserved", retina_license)
            release_cluster_resource(k_server, retina_license.name)


def _get_resource_username(resource: ClusterResource, k_server: Kubernetes) -> str:
    """
    Get resource username
    """
    try:
        return str(resource.get_user_name(k_server))
    except AttributeError:
        return ""


if __name__ == "__main__":
    main()

