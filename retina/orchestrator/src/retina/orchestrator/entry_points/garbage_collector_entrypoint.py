#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Entrypoint to garbage collector.
"""

import argparse

from retina.orchestrator.entry_points.utils import set_default_colored_logger
from retina.orchestrator.orchestration_network import OrchestratorManager


def main():
    """
    Entrypoint to garbage collector.
    """
    parser = argparse.ArgumentParser(description="Garbage collector.")
    parser.add_argument(
        "--mode",
        choices=["demolition"],
        help="In demolition mode it will delete all the orchestration network in the cluster",
    )
    parser.add_argument("--in-cluster", action="store_true", help="Running inside a cluster.")
    parser.add_argument("--dryrun", action="store_true", help="Only list the elements to delete.")

    set_default_colored_logger()

    args = parser.parse_args()
    mode = args.mode
    in_cluster = args.in_cluster
    dryrun = args.dryrun

    orch_manager = OrchestratorManager(is_incluster=in_cluster)
    if mode == "demolition":
        orch_manager.delete_all_orchestration_network(dryrun)


if __name__ == "__main__":
    main()
