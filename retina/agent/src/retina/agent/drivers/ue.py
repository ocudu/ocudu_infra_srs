#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
UE Base
"""

import logging
from abc import ABCMeta
from dataclasses import dataclass
from datetime import datetime
from time import sleep
from typing import Tuple

import grpc
from google.protobuf.empty_pb2 import Empty
from retina.protocol.base_pb2 import Subscriber, UEDefinition
from retina.protocol.ue_pb2 import IPerfDir, IPerfProto, IPerfRequest
from retina.protocol.ue_pb2_grpc import UEServicer

from retina.agent.drivers.base import BaseDriver, notify_grpc_exception
from retina.agent.parameters import testbed_defaults, ue_defaults
from retina.agent.tools.time import now_timestamp_file


@dataclass
class SubscriberWithStatus:
    """
    Subscriber info
    """

    subscriber: Subscriber
    subscriber_id: int
    started: bool = False


class UEDriver(UEServicer, BaseDriver, metaclass=ABCMeta):
    """
    UE Base Driver
    """

    # Extra time budget (on top of request.duration) for iperf process
    _IPERF_EXTRA_LIFETIME: float = 10.0
    _IPERF_RETRIES: int = 5
    _IPERF_SLEEP_BETWEEN_RETRIES: int = 1

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_traffic_timestamp = datetime.fromtimestamp(0)

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> UEDefinition:
        return UEDefinition(
            subscriber=self._get_subscriber(),
            zmq_ip=testbed_defaults.ip_zmq,
            zmq_port_array=[
                testbed_defaults.port_array[i]
                for i in range(ue_defaults.num_cells * max(ue_defaults.nof_antennas_dl, ue_defaults.nof_antennas_ul))
            ],
        )

    def _get_subscriber(self) -> Subscriber:
        return Subscriber(
            imsi=testbed_defaults.imsi,
            k=testbed_defaults.k,
            algo_str=testbed_defaults.sim_algo,
            opc=testbed_defaults.opc,
            amf=testbed_defaults.amf,
            tel=testbed_defaults.tel,
            sd=testbed_defaults.sd,
        )

    def _get_iperf_arg_dict(self, request: IPerfRequest) -> dict:
        args: dict = {
            "-c": str(request.server.ip),
            "-p": str(request.server.port),
            "-t": str(request.duration),
        }
        if request.bitrate:
            args["-b"] = str(request.bitrate)
        if request.packet_length:
            args["-l"] = str(request.packet_length)
        if request.tos:
            args["-S"] = str(request.tos)

        if request.proto is IPerfProto.UDP:  # pylint: disable=no-member
            args["-u"] = None
        if request.direction is IPerfDir.DOWNLINK:  # pylint: disable=no-member
            args["-R"] = None
        elif request.direction is IPerfDir.BIDIRECTIONAL:  # pylint: disable=no-member
            args["--bidir"] = None

        args["--logfile"] = self.get_filepath_in_report_folder(
            f"iperf3_{request.server.ip}_{request.server.port}" f"_{now_timestamp_file()}.log"
        )

        return args

    def _get_iperf_binary(self, context: grpc.ServicerContext) -> Tuple[str, ...]:  # pylint: disable=unused-argument
        return ("iperf3",)

    def _run_iperf(self, arg_dict: dict, timeout: float, context: grpc.ServicerContext):
        cmd = [*self._get_iperf_binary(context)]
        cmd += [x for l in [[k, v] if v else [k] for k, v in arg_dict.items()] for x in l]
        logging.info("IPerf Client executed: %s", " ".join(cmd))

        with notify_grpc_exception(context):
            for _ in range(self._IPERF_RETRIES):
                try:
                    for line in self._executor.run_binary(
                        *cmd,
                        keeplinebreaks=False,
                        timeout=timeout,
                        raise_if_exit_code=True,
                    ):
                        logging.debug(line)
                except TimeoutError:
                    logging.warning("IPerf Client killed [not self stopped]: %s", " ".join(cmd))
                except ChildProcessError as err:
                    logging.warning("IPerf Client died with exit code %s: %s", str(err), " ".join(cmd))
                    sleep(self._IPERF_SLEEP_BETWEEN_RETRIES)
                    continue  # Try again
                break
            else:
                raise ChildProcessError("IPerf can not run")

    def IPerf(self, request: IPerfRequest, context: grpc.ServicerContext) -> Empty:
        arg_dict = self._get_iperf_arg_dict(request)
        self._run_iperf(arg_dict, request.duration + self._IPERF_EXTRA_LIFETIME, context)
        self._last_traffic_timestamp = datetime.now()
        return Empty()
