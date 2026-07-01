# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Traffic-related steps
"""

import logging
from concurrent.futures import as_completed, ThreadPoolExecutor
from functools import partial
from time import sleep
from typing import Dict, List, Tuple

import grpc
import pytest
from google.protobuf.text_format import MessageToString
from google.protobuf.wrappers_pb2 import StringValue
from retina.client.exception import ErrorReportedByAgent
from retina.protocol import FiveGCClient, UEClient
from retina.protocol.base_pb2 import PingRequest, PingResponse
from retina.protocol.fivegc_pb2 import IPerfResponse
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.ue_pb2 import IPerfDir, IPerfProto, IPerfRequest, UEAttachedInfo
from retina.protocol.ue_pb2_grpc import UEStub


def ping(
    *,  # This enforces keyword-only arguments
    ue_attach_info_dict: Dict[UEClient, UEAttachedInfo],
    fivegc: FiveGCClient,
    ping_count,
    time_step: int = 0,
    ping_interval: float = 1.0,
):
    """
    Ping command between an UE and a 5GC
    """
    ping_task_array = ping_start(
        ue_attach_info_dict=ue_attach_info_dict,
        fivegc=fivegc,
        ping_count=ping_count,
        time_step=time_step,
        ping_interval=ping_interval,
    )
    ping_wait_until_finish(ping_task_array)


def ping_start(
    *,  # This enforces keyword-only arguments
    ue_attach_info_dict: Dict[UEClient, UEAttachedInfo],
    fivegc: FiveGCClient,
    ping_count,
    time_step: float = 0,
    ping_interval: float = 1.0,
) -> List[grpc.Future]:
    """
    Ping command between an UE and a 5GC
    """

    # Launch ping (ue -> 5gc and 5gc -> ue) for each attached ue in parallel

    ping_task_array: List[grpc.Future] = []
    for ue_stub, ue_attached_info in ue_attach_info_dict.items():
        ue_to_fivegc: grpc.Future = ue_stub.Ping.future(
            PingRequest(address=ue_attached_info.ipv4_gateway, count=ping_count, interval=ping_interval)
        )
        ue_to_fivegc.add_done_callback(partial(_print_ping_result, f"[{ue_attached_info.ipv4}] UE -> 5GC"))
        fivegc_to_ue: grpc.Future = fivegc.Ping.future(PingRequest(address=ue_attached_info.ipv4, count=ping_count))
        fivegc_to_ue.add_done_callback(partial(_print_ping_result, f"[{ue_attached_info.ipv4}] 5GC -> UE"))
        ping_task_array.append(ue_to_fivegc)
        ping_task_array.append(fivegc_to_ue)
        sleep(time_step)

    return ping_task_array


def ping_wait_until_finish(ping_task_array: List[grpc.Future]) -> None:
    """
    Wait until the requested ping has finished.
    """
    ping_success = True
    for ping_task in ping_task_array:
        ping_success &= ping_task.result().status

    if not ping_success:
        pytest.fail("Ping. Some packages got lost.")


def _print_ping_result(msg: str, task: grpc.Future):
    """
    Print ping result
    """
    log_fn = logging.info
    try:
        result: PingResponse = task.result()
        if not result.status:
            log_fn = logging.error
        log_fn("Ping %s:\n%s", msg, MessageToString(result, indent=2))
    except (grpc.RpcError, grpc.FutureCancelledError, grpc.FutureTimeoutError) as err:
        if isinstance(err, grpc.RpcError):
            logging.error(ErrorReportedByAgent(err))


def ping_from_5gc(
    *,  # This enforces keyword-only arguments
    ue_attach_info_dict: Dict[UEClient, UEAttachedInfo],
    fivegc: FiveGCClient,
    ping_count,
    time_step: int = 0,
):
    """
    Ping command from a 5GC to a UE
    """
    ping_task_array = ping_start_from_5gc(
        ue_attach_info_dict=ue_attach_info_dict, fivegc=fivegc, ping_count=ping_count, time_step=time_step
    )
    ping_wait_until_finish(ping_task_array)


def ping_start_from_5gc(
    *,  # This enforces keyword-only arguments
    ue_attach_info_dict: Dict[UEClient, UEAttachedInfo],
    fivegc: FiveGCClient,
    ping_count,
    time_step: float = 0,
) -> List[grpc.Future]:
    """
    Ping command between a 5GC and an UE
    """

    # Launch ping (5gc -> ue) for each attached ue in parallel

    ping_task_array: List[grpc.Future] = []
    for ue_attached_info in ue_attach_info_dict.values():
        fivegc_to_ue: grpc.Future = fivegc.Ping.future(PingRequest(address=ue_attached_info.ipv4, count=ping_count))
        fivegc_to_ue.add_done_callback(partial(_print_ping_result, f"[{ue_attached_info.ipv4}] 5GC -> UE"))
        ping_task_array.append(fivegc_to_ue)
        sleep(time_step)

    return ping_task_array


# pylint: disable=too-many-arguments,too-many-positional-arguments
def iperf_parallel(
    *,  # This enforces keyword-only arguments
    ue_attach_info_dict: Dict[UEClient, UEAttachedInfo],
    fivegc: FiveGCStub,
    protocol: "IPerfProto.ValueType",
    direction: "IPerfDir.ValueType",
    iperf_duration: int,
    bitrate: int,
    packet_length: int = 0,
    bitrate_threshold_ratio: float = 0,  # real_bitrate > (bitrate_threshold_ratio * ideal_bitrate)
    parallel_iperfs: int = 8,
) -> List[IPerfResponse]:
    """
    iperf command between multiple UEs and a 5GC. Runs at <parallel_iperfs> in parallel.
    """

    iperf_result_list: List[IPerfResponse] = []

    with ThreadPoolExecutor(max_workers=parallel_iperfs) as executor:
        future_array = (
            executor.submit(
                iperf_sequentially,
                ue_stub=ue_stub,
                ue_attached_info=ue_attached_info,
                fivegc=fivegc,
                protocol=protocol,
                direction=direction,
                iperf_duration=iperf_duration,
                bitrate=bitrate,
                packet_length=packet_length,
                bitrate_threshold_ratio=bitrate_threshold_ratio,
            )
            for ue_stub, ue_attached_info in ue_attach_info_dict.items()
        )

        iperf_success = True
        for future in as_completed(future_array):
            iperf_response = future.result()
            iperf_success &= iperf_response[0]
            iperf_result_list.append(iperf_response[1])

    if not iperf_success:
        pytest.fail("iperf did not achieve the expected data rate.")

    return iperf_result_list


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def iperf_sequentially(
    *,  # This enforces keyword-only arguments
    ue_stub: UEStub,
    ue_attached_info: UEAttachedInfo,
    fivegc: FiveGCStub,
    protocol: "IPerfProto.ValueType",
    direction: "IPerfDir.ValueType",
    iperf_duration: int,
    bitrate: int,
    packet_length: int = 0,
    bitrate_threshold_ratio: float = 0,  # real_bitrate > (bitrate_threshold_ratio * ideal_bitrate)
    max_retries: int = 5,
    sleep_between_retries: int = 3,
) -> Tuple[bool, IPerfResponse]:
    """
    iperf command between an UE and a 5GC
    """

    for _ in range(max_retries):
        try:
            task, iperf_request = iperf_start(
                ue_stub=ue_stub,
                ue_attached_info=ue_attached_info,
                fivegc=fivegc,
                protocol=protocol,
                direction=direction,
                duration=iperf_duration,
                bitrate=bitrate,
                packet_length=packet_length,
            )
            sleep(iperf_duration)
            iperf_success, iperf_data = iperf_wait_until_finish(
                ue_attached_info=ue_attached_info,
                fivegc=fivegc,
                task=task,
                iperf_request=iperf_request,
                bitrate_threshold_ratio=bitrate_threshold_ratio,
            )
            if iperf_success:
                return iperf_success, iperf_data
        except grpc.RpcError as err:
            logging.warning(
                "Iperf %s [%s %s] failed due to %s",
                ue_attached_info.ipv4,
                _iperf_proto_to_str(protocol),
                _iperf_dir_to_str(direction),
                ErrorReportedByAgent(err),
            )
        sleep(sleep_between_retries)

    return False, IPerfResponse()


# pylint: disable=too-many-arguments,too-many-positional-arguments
def iperf_start(
    *,  # This enforces keyword-only arguments
    ue_stub: UEStub,
    ue_attached_info: UEAttachedInfo,
    fivegc: FiveGCStub,
    protocol: "IPerfProto.ValueType",
    direction: "IPerfDir.ValueType",
    duration: int,
    bitrate: int,
    packet_length: int = 0,
) -> Tuple[grpc.Future, IPerfRequest]:
    """
    Start a Iperf and keep it running
    """

    iperf_request = IPerfRequest(
        server=fivegc.StartIPerfService(StringValue(value=ue_attached_info.ipv4_gateway)),
        duration=duration,
        direction=direction,
        proto=protocol,
        bitrate=bitrate,
        packet_length=packet_length,
    )

    # Run iperf
    task: grpc.Future = ue_stub.IPerf.future(iperf_request)

    logging.info(
        "Iperf %s [%s %s] started",
        ue_attached_info.ipv4,
        _iperf_proto_to_str(protocol),
        _iperf_dir_to_str(direction),
    )

    return (task, iperf_request)


def iperf_wait_until_finish(
    *,  # This enforces keyword-only arguments
    ue_attached_info: UEAttachedInfo,
    fivegc: FiveGCStub,
    task: grpc.Future,
    iperf_request: IPerfRequest,
    bitrate_threshold_ratio: float = 0,  # real_bitrate > (bitrate_threshold_ratio * ideal_bitrate)
) -> Tuple[bool, IPerfResponse]:
    """
    Wait until the requested iperf has finished.
    """

    # Stop server, get results and print it
    try:
        task.result()
        iperf_data: IPerfResponse = fivegc.StopIPerfService(iperf_request.server)
        logging.info(
            "Iperf %s [%s %s]:\n%s",
            ue_attached_info.ipv4,
            _iperf_proto_to_str(iperf_request.proto),
            _iperf_dir_to_str(iperf_request.direction),
            MessageToString(iperf_data, indent=2),
        )
    except grpc.RpcError as err:
        if ErrorReportedByAgent(err).code is grpc.StatusCode.UNAVAILABLE:
            raise err from None
        logging.warning(
            "Iperf %s [%s %s] failed due to %s",
            ue_attached_info.ipv4,
            _iperf_proto_to_str(iperf_request.proto),
            _iperf_dir_to_str(iperf_request.direction),
            ErrorReportedByAgent(err),
        )
        return (False, IPerfResponse())

    # Assertion
    iperf_success = True
    if (
        iperf_request.direction in (IPerfDir.DOWNLINK, IPerfDir.BIDIRECTIONAL)
        and iperf_data.downlink.bits_per_second <= bitrate_threshold_ratio * iperf_request.bitrate
    ):
        logging.warning(
            "Downlink bitrate too low. Requested: %s - Measured: %s",
            iperf_request.bitrate,
            iperf_data.downlink.bits_per_second,
        )
        iperf_success = False
    if (
        iperf_request.direction in (IPerfDir.UPLINK, IPerfDir.BIDIRECTIONAL)
        and iperf_data.uplink.bits_per_second <= bitrate_threshold_ratio * iperf_request.bitrate
    ):
        logging.warning(
            "Uplink bitrate too low. Requested: %s - Measured: %s",
            iperf_request.bitrate,
            iperf_data.uplink.bits_per_second,
        )
        iperf_success = False
    return (iperf_success, iperf_data)


def _iperf_proto_to_str(proto):
    return {IPerfProto.TCP: "tcp", IPerfProto.UDP: "udp"}[proto]


def _iperf_dir_to_str(direction):
    return {
        IPerfDir.DOWNLINK: "downlink",
        IPerfDir.UPLINK: "uplink",
        IPerfDir.BIDIRECTIONAL: "bidirectional",
    }[direction]
