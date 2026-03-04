# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
5GC Base
"""

import json
import logging
import os
from abc import ABCMeta
from contextlib import suppress
from typing import Any, Dict, List, Optional, Tuple

import grpc
import psutil
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import StringValue, UInt32Value
from retina.protocol.base_pb2 import FiveGCDefinition, IPerfServer, StopResponse, SubscriberArray
from retina.protocol.fivegc_pb2 import IPerfResponse, IPerfSummary
from retina.protocol.fivegc_pb2_grpc import FiveGCServicer

from retina.agent.drivers.base import BaseDriver, notify_grpc_exception
from retina.agent.parameters import fivegc_defaults, testbed_defaults
from retina.agent.tools.time import now_timestamp_file


class FiveGCDriver(FiveGCServicer, BaseDriver, metaclass=ABCMeta):
    """
    5GC Driver
    """

    def __init__(self, *args, **kwargs) -> None:
        self._iperf_process_dict: Dict[Tuple[str, int], psutil.Process] = {}
        self._iperf_log_dict: Dict[Tuple[str, int], str] = {}
        super().__init__(*args, **kwargs)

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> FiveGCDefinition:
        return FiveGCDefinition(
            amf_ip=testbed_defaults.ip,
            amf_port=38412,  # NGAP port, see TS 38.412, section 7.
            tun_ip=fivegc_defaults.tun_subnet,
            tun_mask=fivegc_defaults.tun_mask,
        )

    def _port_in_use(self, port: int, address: str = "") -> bool:
        for line in self._executor.run_binary("ss", "-tulpn", raise_if_exit_code=False):
            if f"{address}:{port}" in line:
                return True
        return False

    def _get_free_port(self, address: str = "") -> int:
        while True:
            for i in range(5000, 6000):
                if not self._port_in_use(i, address):
                    return i

    def StartIPerfService(self, request: StringValue, context: grpc.ServicerContext) -> IPerfServer:
        server_ip = request.value
        server_port = self._get_free_port()

        if (server_ip, server_port) in self._iperf_process_dict:
            self.StopIPerfService(IPerfServer(ip=server_ip, port=server_port), context)

        log = self.get_filepath_in_report_folder(f"iperf3_{server_ip}_{server_port}_{now_timestamp_file()}.json")

        cmd = (
            "iperf3",
            "-s",
            "-B",
            server_ip,
            "-p",
            str(server_port),
            "--one-off",
            "-J",
            "--logfile",
            log,
        )

        logging.info("IPerf Server executed: %s", " ".join(cmd))

        self._iperf_process_dict[(server_ip, server_port)] = self._executor.create_process(*cmd)
        self._iperf_log_dict[(server_ip, server_port)] = log

        return IPerfServer(ip=server_ip, port=server_port)

    def StopIPerfService(self, request: IPerfServer, context: grpc.ServicerContext) -> IPerfResponse:
        process = self._iperf_process_dict.pop((request.ip, request.port), None)
        if process is not None and self._executor.is_process_alive(process):
            self._executor.exit_process(process)

        log = self._iperf_log_dict.pop((request.ip, request.port), "")
        if log:
            # In case Iperf is executed remotely we need to copy the output json to the agent.
            self._executor.copy_file(log, log, True)

            with open(log, "r", encoding="utf-8") as file_descriptor:
                # iperf json concatenates multiple dictionaries without any separation
                # we convert it into an array, so it can be parsed
                raw_data = "[" + file_descriptor.read().replace("}" + os.linesep + "{", "},{") + "]"

            if raw_data:
                # We only want the end section of the first dictionary
                with suppress(SyntaxError, IndexError):
                    result_dict = json.loads(raw_data, object_pairs_hook=_concatenate_duplicate_keys)[0]["end"]
                    if result_dict:
                        for label in ("sum_sent_bidir_reverse", "sum_sent"):
                            _, downlink = _parse_iperf_result_dict(result_dict, label)
                            if downlink is not None:
                                break
                        for label in ("sum_received",):
                            uplink, _ = _parse_iperf_result_dict(result_dict, label)
                            if uplink is not None:
                                break

                        return IPerfResponse(
                            downlink=downlink if downlink is not None else IPerfSummary(),
                            uplink=uplink if uplink is not None else IPerfSummary(),
                        )

        with notify_grpc_exception(context):
            raise ChildProcessError("IPerf Data Invalid") from None

    def Stop(self, request: UInt32Value, context: Optional[grpc.ServicerContext]) -> StopResponse:
        for server_ip, server_port in dict(self._iperf_process_dict):
            self.StopIPerfService(IPerfServer(ip=server_ip, port=server_port), context)
        return super().Stop(request, context)

    def GetImsRegisteredUESubscriberArray(self, request: Empty, context: grpc.ServicerContext) -> SubscriberArray:
        return SubscriberArray()


def _concatenate_duplicate_keys(ordered_pairs: List[Tuple[Any, Any]]) -> Dict:
    """
    If there is a duplicate key, we convert it in an array and add all values
    """
    dictionary: Dict[Any, Any] = {}
    for key, value in ordered_pairs:
        if key in dictionary:
            if isinstance(dictionary[key], list):
                dictionary[key] = [*dictionary[key], value]
            else:
                dictionary[key] = [dictionary[key], value]
        else:
            dictionary[key] = value
    return dictionary


def _parse_iperf_result_dict(result_dict: Dict, key: str) -> Tuple[Optional[IPerfSummary], Optional[IPerfSummary]]:
    """
    Returns [sender_false, sender_true] for the specified key
    """
    to_return = [None, None]
    if key in result_dict:
        if not isinstance(result_dict[key], list):
            result_dict[key] = [result_dict[key]]
        for summary_dict in result_dict[key]:
            to_return[summary_dict["sender"]] = IPerfSummary(
                bytes=summary_dict["bytes"],
                bits_per_second=summary_dict["bits_per_second"],
                seconds=summary_dict["seconds"],
                lost_packets=summary_dict.get("lost_packets", 0),
                packets=summary_dict.get("packets", 0),
                retransmits=summary_dict.get("retransmits", 0),
            )
    return (to_return[0], to_return[1])
