# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Agent Main Entrypoint
"""

import argparse
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import grpc
from google.protobuf.wrappers_pb2 import UInt32Value
from grpc_health.v1.health_pb2 import HealthCheckResponse
from grpc_health.v1.health_pb2_grpc import add_HealthServicer_to_server
from retina.protocol.base_pb2_grpc import add_BaseServicer_to_server, Base
from retina.protocol.channel_emulator_pb2_grpc import (
    add_ChannelEmulatorServicer_to_server,
    ChannelEmulator,
    ChannelEmulatorServicer,
)
from retina.protocol.fivegc_pb2_grpc import add_FiveGCServicer_to_server, FiveGC, FiveGCServicer
from retina.protocol.gnb_pb2_grpc import (
    add_CUServicer_to_server,
    add_DUServicer_to_server,
    add_GNBServicer_to_server,
    CU,
    CUServicer,
    DU,
    DUServicer,
    GNB,
    GNBServicer,
)
from retina.protocol.ric_pb2_grpc import add_NearRtRicServicer_to_server, NearRtRic, NearRtRicServicer
from retina.protocol.ue_pb2_grpc import add_UEServicer_to_server, UE, UEServicer

from retina.agent.app.logger import retina_log_setup
from retina.agent.drivers.amarisoft_5gc import LocalAmarisoft5gc, RemoteAmarisoft5gc
from retina.agent.drivers.amarisoft_ue import LocalAmarisoftUe, RemoteAmarisoftUe
from retina.agent.drivers.android import AdbAndroidUE
from retina.agent.drivers.base import BaseDriver
from retina.agent.drivers.flexric import LocalFlexricRic
from retina.agent.drivers.health import RetinaHealth
from retina.agent.drivers.ntn_channel_emulator import LocalNtnChannelEmulator
from retina.agent.drivers.ocudu_cu import LocalOcuduCu
from retina.agent.drivers.ocudu_cudu import LocalOcuduCuDu
from retina.agent.drivers.ocudu_du import LocalOcuduDu
from retina.agent.drivers.ocudu_gnb import LocalOcuduGnb, RemoteOcuduGnb
from retina.agent.drivers.open5gs_5gc import LocalOpen5gs5gc
from retina.agent.drivers.srs_ue import LocalSrsUe
from retina.agent.tools.time import now_timestamp_file

_DRIVER_CODENAME_DICT: Dict[str, BaseDriver] = {
    "amarisoft-ue": LocalAmarisoftUe,
    "amarisoft-ue-remote": RemoteAmarisoftUe,
    "android": AdbAndroidUE,
    "ocudu-gnb": LocalOcuduGnb,
    "ocudu-gnb-remote": RemoteOcuduGnb,
    "ocudu-cudu": LocalOcuduCuDu,
    "ocudu-cu": LocalOcuduCu,
    "ocudu-du": LocalOcuduDu,
    "srs-ue": LocalSrsUe,
    "open5gs-5gc": LocalOpen5gs5gc,
    "flexric-ric": LocalFlexricRic,
    "ntn-channel-emulator": LocalNtnChannelEmulator,
    "amarisoft-5gc": LocalAmarisoft5gc,
    "amarisoft-5gc-remote": RemoteAmarisoft5gc,
}


@dataclass(frozen=True, eq=True)
class _GrpcConfig:
    server_ports: list[int]
    keep_alive_timeout: int
    maximum_workers: int
    maximum_concurrent_rpcs: int


@dataclass(frozen=True, eq=True)
class _ParseOutput:
    codename: str
    resource_folder: str
    report_folder: str
    grpc_config: _GrpcConfig


def _argument_parser() -> _ParseOutput:
    """
    Parse inputs and load configuration from conf file
    """
    parser = argparse.ArgumentParser(description="Retina Agent")
    parser.add_argument(
        "codename",
        type=str,
        help="Driver to launch",
        choices=_DRIVER_CODENAME_DICT.keys(),
    )
    parser.add_argument("--report-folder", type=str, help="Report folder path", default=str(Path.cwd()))
    parser.add_argument("--resource-folder", type=str, help="Resource folder path", default="/etc/retina/resources")
    parser.add_argument("--server-ports", type=int, nargs="*", help="gRPC server ports", default=(50051,))
    parser.add_argument(
        "--keep-alive-timeout", type=int, help="gRPC keep alive timeout in seconds. Default 1h", default=3600
    )
    parser.add_argument("--maximum-workers", type=int, help="gRPC maximum workers", default=12)
    parser.add_argument(
        "--maximum-concurrent-rpcs", type=int, help="gRPC maximum concurrent rpcs. Use -1 for no limit", default=-1
    )

    args = parser.parse_args()

    return _ParseOutput(
        codename=args.codename,
        resource_folder=args.resource_folder,
        report_folder=args.report_folder,
        grpc_config=_GrpcConfig(
            server_ports=args.server_ports,
            keep_alive_timeout=args.keep_alive_timeout,
            maximum_workers=args.maximum_workers,
            maximum_concurrent_rpcs=args.maximum_concurrent_rpcs,
        ),
    )


def _agent_factory(
    codename: str,
    report_folder: str,
    resource_folder: str,
    grpc_config: _GrpcConfig,
):
    # Server
    server = grpc.server(
        ThreadPoolExecutor(max_workers=grpc_config.maximum_workers),
        maximum_concurrent_rpcs=(
            None if grpc_config.maximum_concurrent_rpcs <= 0 else grpc_config.maximum_concurrent_rpcs
        ),
    )
    for port in grpc_config.server_ports:
        server.add_insecure_port(f"[::]:{port}")

    # Servicer
    health_servicer = RetinaHealth(grpc_config.keep_alive_timeout)
    health_servicer.set("", HealthCheckResponse.SERVING)
    add_HealthServicer_to_server(health_servicer, server)

    retina_servicer = _DRIVER_CODENAME_DICT[codename](report_folder=report_folder, resource_folder=resource_folder)
    health_servicer.set(Base.__name__, HealthCheckResponse.SERVING)
    add_BaseServicer_to_server(retina_servicer, server)
    if isinstance(retina_servicer, UEServicer):
        health_servicer.set(UE.__name__, HealthCheckResponse.SERVING)
        add_UEServicer_to_server(retina_servicer, server)
    if isinstance(retina_servicer, GNBServicer):
        health_servicer.set(GNB.__name__, HealthCheckResponse.SERVING)
        add_GNBServicer_to_server(retina_servicer, server)
    if isinstance(retina_servicer, CUServicer):
        health_servicer.set(CU.__name__, HealthCheckResponse.SERVING)
        add_CUServicer_to_server(retina_servicer, server)
    if isinstance(retina_servicer, DUServicer):
        health_servicer.set(DU.__name__, HealthCheckResponse.SERVING)
        add_DUServicer_to_server(retina_servicer, server)
    if isinstance(retina_servicer, FiveGCServicer):
        health_servicer.set(FiveGC.__name__, HealthCheckResponse.SERVING)
        add_FiveGCServicer_to_server(retina_servicer, server)
    if isinstance(retina_servicer, NearRtRicServicer):
        health_servicer.set(NearRtRic.__name__, HealthCheckResponse.SERVING)
        add_NearRtRicServicer_to_server(retina_servicer, server)
    if isinstance(retina_servicer, ChannelEmulatorServicer):
        health_servicer.set(ChannelEmulator.__name__, HealthCheckResponse.SERVING)
        add_ChannelEmulatorServicer_to_server(retina_servicer, server)

    def close():
        logging.info("Closing the agent")
        retina_servicer.Stop(UInt32Value(value=0), None)
        health_servicer.enter_graceful_shutdown()
        server.stop(grace=5)

    retina_servicer.set_shutdown_callback(close)

    # Start
    server.start()
    logging.info(
        "Retina Agent for %s listening at port(s) %s",
        codename,
        ", ".join(map(str, grpc_config.server_ports)),
    )

    signal.signal(signal.SIGINT, lambda signum, frame: close())
    signal.signal(signal.SIGTERM, lambda signum, frame: close())

    server.wait_for_termination()

    logging.info("Agent Closed")


def main():
    """
    Agent Main Entrypoint
    """

    arguments = _argument_parser()
    retina_log_setup(Path(arguments.report_folder).joinpath("agent-log-" + now_timestamp_file() + ".log").resolve())
    _agent_factory(arguments.codename, arguments.report_folder, arguments.resource_folder, arguments.grpc_config)


if __name__ == "__main__":
    main()
