# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Steps related with stubs / resources
"""

import logging
from concurrent.futures import as_completed, ThreadPoolExecutor
from contextlib import contextmanager, suppress
from time import sleep
from typing import Dict, Generator, List, Optional, Sequence, Tuple

import grpc
import pytest
from _pytest.outcomes import Failed
from google.protobuf.empty_pb2 import Empty
from google.protobuf.text_format import MessageToString
from google.protobuf.wrappers_pb2 import StringValue, UInt32Value
from retina.client.exception import ErrorReportedByAgent
from retina.launcher.artifacts import RetinaTestData
from retina.protocol import RanStub
from retina.protocol.base_pb2 import (
    CUCPDefinition,
    DUDefinition,
    FiveGCDefinition,
    GNBDefinition,
    Metrics,
    NearRtRicDefinition,
    PingRequest,
    PingResponse,
    PLMN,
    StartInfo,
    StopResponse,
    UEDefinition,
)
from retina.protocol.channel_emulator_pb2_grpc import ChannelEmulatorStub
from retina.protocol.exit_codes import exit_code_to_message
from retina.protocol.fivegc_pb2 import FiveGCStartInfo, IPerfResponse
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2 import CUCPStartInfo, CUStartInfo, CUUPStartInfo, DUStartInfo, GNBStartInfo
from retina.protocol.gnb_pb2_grpc import CUCPStub, CUStub, CUUPStub, DUStub, GNBStub
from retina.protocol.ric_pb2 import KpmMonXappRequest, NearRtRicStartInfo, RcXappRequest
from retina.protocol.ric_pb2_grpc import NearRtRicStub
from retina.protocol.ue_pb2 import (
    IPerfDir,
    IPerfProto,
    IPerfRequest,
    UEAttachedInfo,
    UEStartInfo,
)
from retina.protocol.ue_pb2_grpc import UEStub

RF_MAX_TIMEOUT: int = 5 * 60  # Time enough in RF when loading a new image in the sdr
UE_STARTUP_TIMEOUT: int = RF_MAX_TIMEOUT
GNB_STARTUP_TIMEOUT: int = 2  # GNB delay (we wait x seconds and check it's still alive). UE later and has a big timeout
FIVEGC_STARTUP_TIMEOUT: int = RF_MAX_TIMEOUT
ATTACH_TIMEOUT: int = 90
INTER_UE_START_PERIOD: int = 0


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def start_and_attach(
    *,  # This enforces keyword-only arguments
    ue_array: Sequence[UEStub],
    gnb: GNBStub,
    fivegc: FiveGCStub,
    ue_startup_timeout: int = UE_STARTUP_TIMEOUT,
    gnb_startup_timeout: int = GNB_STARTUP_TIMEOUT,
    fivegc_startup_timeout: int = FIVEGC_STARTUP_TIMEOUT,
    gnb_pre_cmd: Tuple[str, ...] = tuple(),
    gnb_post_cmd: Tuple[str, ...] = tuple(),
    attach_timeout: int = ATTACH_TIMEOUT,
    plmn: Optional[PLMN] = None,
    inter_ue_start_period=INTER_UE_START_PERIOD,
    ric: Optional[NearRtRicStub] = None,
    channel_emulator: Optional[ChannelEmulatorStub] = None,
) -> Dict[UEStub, UEAttachedInfo]:
    """
    Start stubs & wait until attach
    """
    start_network(
        ue_array=ue_array,
        gnb_array=[gnb],
        fivegc_array=[fivegc],
        gnb_startup_timeout=gnb_startup_timeout,
        fivegc_startup_timeout=fivegc_startup_timeout,
        gnb_pre_cmd=gnb_pre_cmd,
        gnb_post_cmd=gnb_post_cmd,
        plmn=plmn,
        ric=ric,
        channel_emulator=channel_emulator,
    )

    return ue_start_and_attach(
        ue_array=ue_array,
        du_definition=[gnb.GetDefinition(UInt32Value(value=0)).du_definition],
        fivegc_array=[fivegc],
        ue_startup_timeout=ue_startup_timeout,
        attach_timeout=attach_timeout,
        inter_ue_start_period=inter_ue_start_period,
        channel_emulator=channel_emulator,
    )


def _get_hplmn(imsi: str) -> PLMN:
    """
    Obtain home PLMN (HPLMN) from IMSI prefix as specified in TS 23.003 Sec. 2.2
    """
    hplmn = PLMN()
    hplmn.mcc = imsi[0:3]
    hplmn.mnc = imsi[3:5]
    return hplmn


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
def start_network(
    *,  # This enforces keyword-only arguments
    ue_array: Sequence[UEStub],
    fivegc_array: Sequence[FiveGCStub],
    gnb_array: Optional[Sequence[GNBStub]] = None,
    cu: Optional[CUStub] = None,
    cu_cp_array: Optional[Sequence[CUCPStub]] = None,
    cu_up_array: Optional[Sequence[CUUPStub]] = None,
    du_array: Optional[Sequence[DUStub]] = None,
    gnb_startup_timeout: int = GNB_STARTUP_TIMEOUT,
    fivegc_startup_timeout: int = FIVEGC_STARTUP_TIMEOUT,
    gnb_pre_cmd: Tuple[str, ...] = tuple(),
    gnb_post_cmd: Tuple[str, ...] = tuple(),
    plmn: Optional[PLMN] = None,
    ric: Optional[NearRtRicStub] = None,
    channel_emulator: Optional[ChannelEmulatorStub] = None,
):
    """
    Start Network (5GC + gNB/CU+DU/CUCP+CUUP+DU + RIC(optional))
    """

    if gnb_array and (cu or cu_cp_array or du_array):
        pytest.fail("Either gNB or CU/CUCP and DU array must be provided, not both")

    if (cu and not du_array) or (not cu and du_array and not cu_cp_array):
        pytest.fail("CU and DU must be provided together")

    if (cu_cp_array and not cu_up_array) or (not cu_cp_array and cu_up_array):
        pytest.fail("CUCP and CUUP array must be provided together")

    ue_def_for_gnb = UEDefinition()
    for ue_stub in ue_array:
        ue_def: UEDefinition = ue_stub.GetDefinition(Empty())
        ue_hplmn = _get_hplmn(ue_def.subscriber.imsi)
        if plmn:
            # Warn if UEs have different HPLMNs
            if plmn != ue_hplmn:
                logging.warning(
                    "HPLMN of UE with IMSI [%s] differs from PLMN. Expected MCC=%s MNC=%s",
                    ue_def.subscriber.imsi,
                    plmn.mcc,
                    plmn.mnc,
                )
        else:
            # Set PLMN to HPLMN of first UE
            plmn = ue_hplmn
            logging.info("Setting PLMN to HPLMN of first UE. MCC=%s MNC=%s", plmn.mcc, plmn.mnc)
        for fivegc in fivegc_array:
            fivegc.AddUESubscriber(ue_def.subscriber)
        if ue_def.zmq_ip is not None:
            ue_def_for_gnb = ue_def

    fivegc_definition = [
        fivegc_start(fivegc, plmn=plmn, fivegc_startup_timeout=fivegc_startup_timeout) for fivegc in fivegc_array
    ]

    if channel_emulator and ue_def_for_gnb.zmq_ip is not None:
        # Overwrite the ZMQ IP and port, so the GNB connects to the channel emulator.
        channel_emulator_definition = channel_emulator.GetDefinition(Empty())
        ue_def_for_gnb.zmq_ip = channel_emulator_definition.zmq_ip
        ue_def_for_gnb.zmq_port_array[0] = channel_emulator_definition.ul_zmq_port

    ric_definition = None
    if ric:
        ric_startup_timeout = fivegc_startup_timeout
        with handle_start_error(name=f"RIC [{id(ric)}]"):
            # Near-RT RIC Start
            ric.Start(
                NearRtRicStartInfo(
                    start_info=StartInfo(timeout=ric_startup_timeout),
                )
            )
            ric_definition = ric.GetDefinition(Empty())
            logging.info("RIC: %s", MessageToString(ric_definition, indent=2))

    if gnb_array:
        gnb_definitions = [gnb.GetDefinition(UInt32Value(value=idx)) for idx, gnb in enumerate(gnb_array)]
        for idx, gnb in enumerate(gnb_array):
            gnb_start(
                gnb,
                plmn=plmn,
                ue_definition=ue_def_for_gnb,
                fivegc_definition_array=fivegc_definition,
                ric_definition=ric_definition,
                neighbor_cucp_definition=[d.cucp_definition for i, d in enumerate(gnb_definitions) if i != idx],
                startup_timeout=gnb_startup_timeout,
                pre_cmd=gnb_pre_cmd,
                post_cmd=gnb_post_cmd,
            )
        return

    cucp_definitions: Sequence[CUCPDefinition] = tuple()
    if cu:
        cucp_definitions = (cu.GetDefinition(Empty()),)
        with handle_start_error(name=f"CU [{id(cu)}]"):
            # CU Start
            cu.Start(
                CUStartInfo(
                    plmn=plmn,
                    fivegc_definition=fivegc_definition,
                    start_info=StartInfo(
                        timeout=gnb_startup_timeout,
                    ),
                )
            )

    if cu_cp_array:
        cucp_definitions = tuple(cu_cp.GetDefinition(Empty()) for cu_cp in cu_cp_array)
        for cu_cp in cu_cp_array:
            with handle_start_error(name=f"CU-CP [{id(cu_cp)}]"):
                # CU-CP Start
                cu_cp.Start(
                    CUCPStartInfo(
                        plmn=plmn,
                        fivegc_definition=fivegc_definition,
                        start_info=StartInfo(
                            timeout=gnb_startup_timeout,
                        ),
                    )
                )

    if cu_up_array:
        for cu_up in cu_up_array:
            with handle_start_error(name=f"CU-UP [{id(cu_up)}]"):
                # CU-UP Start
                cu_up.Start(
                    CUUPStartInfo(
                        cucp_definition=cucp_definitions,
                        fivegc_definition=fivegc_definition,
                        start_info=StartInfo(
                            timeout=gnb_startup_timeout,
                        ),
                    )
                )

    if du_array:
        for du_id, du_stub in enumerate(du_array):
            with handle_start_error(name=f"DU [{id(du_stub)}]"):
                # DU Start
                du_stub.Start(
                    DUStartInfo(
                        gnb_du_id=du_id,
                        plmn=plmn,
                        num_cells=1,
                        cell_offset=du_id,
                        cucp_definition=(
                            cucp_definitions[du_id] if len(cucp_definitions) > du_id else cucp_definitions[0]
                        ),
                        ue_definition=ue_def_for_gnb,
                        ric_definition=ric_definition,
                        start_info=StartInfo(
                            timeout=gnb_startup_timeout,
                        ),
                    )
                )


def fivegc_start(
    fivegc: FiveGCStub,
    plmn: Optional[PLMN] = PLMN(),
    fivegc_startup_timeout: int = FIVEGC_STARTUP_TIMEOUT,
) -> FiveGCDefinition:
    """Starts a FiveG Core"""

    with handle_start_error(name=f"5GC [{id(fivegc)}]"):
        # 5GC Start
        fivegc.Start(FiveGCStartInfo(plmn=plmn, start_info=StartInfo(timeout=fivegc_startup_timeout)))
    return fivegc.GetDefinition(Empty())


def gnb_start(
    gnb: GNBStub,
    plmn: Optional[PLMN] = PLMN(),
    ue_definition: UEDefinition = UEDefinition(),
    ric_definition: NearRtRicDefinition = NearRtRicDefinition(),
    fivegc_definition_array: Sequence[FiveGCDefinition] = tuple(),
    neighbor_cucp_definition: Sequence[CUCPDefinition] = tuple(),
    startup_timeout: int = GNB_STARTUP_TIMEOUT,
    pre_cmd: Tuple[str, ...] = tuple(),
    post_cmd: Tuple[str, ...] = tuple(),
    cell_offset: int = 0,
) -> GNBDefinition:
    """Starts a gNB"""

    with handle_start_error(name=f"GNB [{id(gnb)}]"):
        # GNB Start
        gnb.Start(
            GNBStartInfo(
                plmn=plmn,
                ue_definition=ue_definition,
                ric_definition=ric_definition,
                fivegc_definition=fivegc_definition_array,
                neighbor_cucp_definition=neighbor_cucp_definition,
                start_info=StartInfo(
                    timeout=startup_timeout,
                    pre_commands=pre_cmd,
                    post_commands=post_cmd,
                ),
            )
        )
    return gnb.GetDefinition(UInt32Value(value=cell_offset))


def ue_start_and_attach(
    *,  # This enforces keyword-only arguments
    ue_array: Sequence[UEStub],
    du_definition: Sequence[DUDefinition],
    fivegc_array: Sequence[FiveGCStub],
    ue_startup_timeout: int = UE_STARTUP_TIMEOUT,
    attach_timeout: int = ATTACH_TIMEOUT,
    inter_ue_start_period: int = INTER_UE_START_PERIOD,
    channel_emulator: Optional[ChannelEmulatorStub] = None,
) -> Dict[UEStub, UEAttachedInfo]:
    """
    Start an array of UEs and wait until attached to already running gnb and 5gc
    """

    ue_start(ue_array, du_definition, fivegc_array, ue_startup_timeout, inter_ue_start_period, channel_emulator)

    # Attach in parallel
    ue_attach_task_dict: Dict[UEStub, grpc.Future] = {
        ue_stub: ue_stub.WaitUntilAttached.future(UInt32Value(value=attach_timeout)) for ue_stub in ue_array
    }
    for ue_stub, task in ue_attach_task_dict.items():
        task.add_done_callback(lambda _task, _ue_stub=ue_stub: _log_attached_ue(_task, _ue_stub))

    ue_attach_info_dict: Dict[UEStub, UEAttachedInfo] = {}
    with suppress(grpc.RpcError):
        ue_attach_info_dict = {
            ue_stub: task.result() for ue_stub, task in ue_attach_task_dict.items()  # Waiting for attach
        }

    if not ue_attach_info_dict:
        pytest.fail("Attach timeout reached")

    return ue_attach_info_dict


def ue_start(
    ue_array: Sequence[UEStub],
    du_definition: Sequence[DUDefinition],
    fivegc_array: Sequence[FiveGCStub],
    ue_startup_timeout: int = UE_STARTUP_TIMEOUT,
    inter_ue_start_period: int = INTER_UE_START_PERIOD,
    channel_emulator: Optional[ChannelEmulatorStub] = None,
):
    """
    Start an array of UEs
    """

    if channel_emulator and du_definition[0].zmq_ip is not None:
        # Overwrite the ZMQ IP and port, so the UE connects to the channel emulator.
        channel_emulator_definition = channel_emulator.GetDefinition(Empty())
        du_definition[0].zmq_ip = channel_emulator_definition.zmq_ip
        du_definition[0].zmq_port_array[0] = channel_emulator_definition.dl_zmq_port

    fivegc_definition = [f.GetDefinition(Empty()) for f in fivegc_array]
    for ue_stub in ue_array:
        with handle_start_error(name=f"UE [{id(ue_stub)}]"):
            ue_stub.Start(
                UEStartInfo(
                    du_definition=du_definition,
                    fivegc_definition=fivegc_definition,
                    start_info=StartInfo(timeout=ue_startup_timeout),
                )
            )
            sleep(inter_ue_start_period)


def start_kpm_mon_xapp(
    *,  # This enforces keyword-only arguments
    ric: NearRtRicStub,
    report_service_style: int = 1,
    metrics: str = "DRB.UEThpDl",
) -> None:
    """
    Start KPM Monitor xAPP in RIC
    """
    xapp_request = KpmMonXappRequest()
    xapp_request.report_service_style = report_service_style
    xapp_request.metrics = metrics
    ric.StartKpmMonXapp(xapp_request)


def stop_kpm_mon_xapp(ric: NearRtRicStub) -> None:
    """
    Stop KPM Monitor xAPP in RIC
    """
    ric.StopKpmMonXapp(Empty())


def start_rc_xapp(
    *, ric: NearRtRicStub, control_service_style: int = 2, action_id: int = 6  # The "*" enforces keyword-only arguments
) -> None:
    """
    Start RC xAPP in RIC, currently only Slice-level PRB quota (Control Style 2, Action Id 6) is supported in Flexric.
    Also, Flexric does not parse the control parameters.
    """
    xapp_request = RcXappRequest()
    xapp_request.control_service_style = control_service_style
    xapp_request.action_id = action_id
    # Parameters
    xapp_request.parameters[7].name = "PLMN Identity"
    xapp_request.parameters[7].value = 1
    xapp_request.parameters[9].name = "SST"
    xapp_request.parameters[9].value = 1
    xapp_request.parameters[10].name = "SD"
    xapp_request.parameters[10].value = 1
    xapp_request.parameters[11].name = "Min PRB Policy Ratio"
    xapp_request.parameters[11].value = 10
    xapp_request.parameters[12].name = "Max PRB Policy Ratio"
    xapp_request.parameters[12].value = 90
    xapp_request.parameters[13].name = "Dedicated PRB Policy Ratio"
    xapp_request.parameters[13].value = 80
    ric.StartRcXapp(xapp_request)


def stop_rc_xapp(ric: NearRtRicStub) -> None:
    """
    Stop RC xAPP in RIC
    """
    ric.StopRcXapp(Empty())


@contextmanager
def handle_start_error(name: str) -> Generator[None, None, None]:
    """
    Fail the test if the stub could not start
    """
    raise_failed = False
    try:
        yield
        logging.info("%s started", name)
    except grpc.RpcError as err:
        if ErrorReportedByAgent(err).code in (grpc.StatusCode.ABORTED, grpc.StatusCode.DEADLINE_EXCEEDED):
            raise_failed = True
        else:
            raise err from None
    if raise_failed:
        raise Failed(msg=f"{name} failed to start", pytrace=True) from None


def _log_attached_ue(future: grpc.Future, ue_stub: UEStub):
    with suppress(grpc.RpcError, ValueError):
        logging.info(
            "UE [%s] attached:\n%s%s ",
            id(ue_stub),
            MessageToString(ue_stub.GetDefinition(Empty()).subscriber, indent=2),
            MessageToString(future.result(), indent=2),
        )


def ping(
    *,  # This enforces keyword-only arguments
    ue_attach_info_dict: Dict[UEStub, UEAttachedInfo],
    fivegc: FiveGCStub,
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
    ue_attach_info_dict: Dict[UEStub, UEAttachedInfo],
    fivegc: FiveGCStub,
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
        ue_to_fivegc.add_done_callback(
            lambda _task, _msg=f"[{ue_attached_info.ipv4}] UE -> 5GC": _print_ping_result(_msg, _task)
        )
        fivegc_to_ue: grpc.Future = fivegc.Ping.future(PingRequest(address=ue_attached_info.ipv4, count=ping_count))
        fivegc_to_ue.add_done_callback(
            lambda _task, _msg=f"[{ue_attached_info.ipv4}] 5GC -> UE": _print_ping_result(_msg, _task)
        )
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
        logging.error(ErrorReportedByAgent(err))


def ping_from_5gc(
    *,  # This enforces keyword-only arguments
    ue_attach_info_dict: Dict[UEStub, UEAttachedInfo],
    fivegc: FiveGCStub,
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
    ue_attach_info_dict: Dict[UEStub, UEAttachedInfo],
    fivegc: FiveGCStub,
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
        fivegc_to_ue.add_done_callback(
            lambda _task, _msg=f"[{ue_attached_info.ipv4}] 5GC -> UE": _print_ping_result(_msg, _task)
        )
        ping_task_array.append(fivegc_to_ue)
        sleep(time_step)

    return ping_task_array


def iperf_parallel(
    *,  # This enforces keyword-only arguments
    ue_attach_info_dict: Dict[UEStub, UEAttachedInfo],
    fivegc: FiveGCStub,
    protocol: IPerfProto,
    direction: IPerfDir,
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


def iperf_sequentially(
    *,  # This enforces keyword-only arguments
    ue_stub: UEStub,
    ue_attached_info: UEAttachedInfo,
    fivegc: FiveGCStub,
    protocol: IPerfProto,
    direction: IPerfDir,
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


def iperf_start(
    *,  # This enforces keyword-only arguments
    ue_stub: UEStub,
    ue_attached_info: UEAttachedInfo,
    fivegc: FiveGCStub,
    protocol: IPerfProto,
    direction: IPerfDir,
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


def validate_ue_registered_via_ims(
    *, ue_stub_array: Sequence[UEStub], core: FiveGCStub  # The "*" enforces keyword-only arguments
) -> None:
    """
    Fails if the UEs are not registered in IMS
    """
    expected_subscriber_array = tuple(
        sorted([ue_stub.GetDefinition(Empty()).subscriber.imsi for ue_stub in ue_stub_array])
    )
    logging.info("IMSI of expected UEs in IMS: %s", expected_subscriber_array)
    registered_subscriber_array = tuple(
        sorted([subscriber.imsi for subscriber in core.GetImsRegisteredUESubscriberArray(Empty()).value])
    )
    logging.info("IMSI of registered UEs in IMS: %s", registered_subscriber_array)
    if expected_subscriber_array != registered_subscriber_array:
        pytest.fail("IMS Registered Subscriber array mismatch!")


def ric_validate_e2_interface(
    *,
    ric: NearRtRicStub,
    kpm_expected: bool = False,
    rc_expected: bool = False,  # The "*" enforces keyword-only arguments
) -> None:
    """
    Fails if E2 was not operating correctly
    """
    ric_summary = ric.GetNearRtRicSummary(Empty())
    logging.info("RIC summary: %s", MessageToString(ric_summary, indent=2))

    if not ric_summary.nof_connected_agents:
        pytest.fail("No E2 agent connected to RIC.")

    if kpm_expected:
        if not ric_summary.nof_connected_xapps:
            pytest.fail("No xApp connected, but expected.")

        if not ric_summary.nof_subscription_reqs or not ric_summary.nof_subscription_reps:
            pytest.fail("No valid RIC subscription received, but expected.")

        if ric_summary.nof_subscription_reqs != ric_summary.nof_subscription_reps:
            pytest.fail("Different number of Subscription Request and Replies.")

        if not ric_summary.nof_ric_indication:
            pytest.fail("No RIC Indiation messages after a successful subscription.")

    if rc_expected:
        if not ric_summary.nof_connected_xapps:
            pytest.fail("No xApp connected, but expected.")

        if not ric_summary.nof_control_reqs or not ric_summary.nof_control_reps:
            pytest.fail("No RIC Control Request received, but expected.")

        if ric_summary.nof_control_reqs != ric_summary.nof_control_reps:
            pytest.fail("Different number of RIC Control Request and Replies.")


# pylint: disable=too-many-branches
def stop(
    *,  # This enforces keyword-only arguments
    ue_array: Sequence[UEStub],
    retina_data: RetinaTestData,
    gnb_array: Optional[Sequence[GNBStub]] = None,
    cu: Optional[CUStub] = None,
    cu_cp_array: Optional[Sequence[CUCPStub]] = None,
    cu_up_array: Optional[Sequence[CUUPStub]] = None,
    du_array: Optional[Sequence[DUStub]] = None,
    fivegc_array: Optional[Sequence[FiveGCStub]] = None,
    ue_stop_timeout: int = 0,  # Auto
    gnb_stop_timeout: int = 0,
    fivegc_stop_timeout: int = 0,
    log_search: bool = True,
    warning_as_errors: bool = True,
    fail_if_kos: bool = False,
    ric: Optional[NearRtRicStub] = None,
    channel_emulator: Optional[ChannelEmulatorStub] = None,
    stop_gnb_first: bool = False,
):
    """
    Stop ue(s), gnb and 5gc, ric
    """
    # Stop
    error_msg_array = []
    if (stop_gnb_first is True) and (gnb_array is not None):
        for index, gnb in enumerate(gnb_array):
            error_message, _ = _stop_stub(
                stub=gnb,
                name=f"GNB_{index+1}",
                retina_data=retina_data,
                timeout=gnb_stop_timeout,
                log_search=log_search,
                warning_as_errors=warning_as_errors,
            )
        error_msg_array.append(error_message)

    for index, ue_stub in enumerate(ue_array):
        error_message, _ = _stop_stub(
            stub=ue_stub,
            name=f"UE_{index+1}",
            retina_data=retina_data,
            timeout=ue_stop_timeout,
            log_search=log_search,
            warning_as_errors=False,
        )
        error_msg_array.append(error_message)

    if (stop_gnb_first is False) and (gnb_array is not None):
        for index, gnb in enumerate(gnb_array):
            error_message, _ = _stop_stub(
                stub=gnb,
                name=f"GNB_{index+1}",
                retina_data=retina_data,
                timeout=gnb_stop_timeout,
                log_search=log_search,
                warning_as_errors=warning_as_errors,
            )
            error_msg_array.append(error_message)

    if du_array is not None:
        for index, du_stub in enumerate(du_array):
            error_message, _ = _stop_stub(
                stub=du_stub,
                name=f"DU_{index+1}",
                retina_data=retina_data,
                timeout=gnb_stop_timeout,
                log_search=log_search,
                warning_as_errors=warning_as_errors,
            )
            error_msg_array.append(error_message)

    if cu is not None:
        error_message, _ = _stop_stub(
            stub=cu,
            name="CU",
            retina_data=retina_data,
            timeout=gnb_stop_timeout,
            log_search=log_search,
            warning_as_errors=warning_as_errors,
        )
        error_msg_array.append(error_message)

    if cu_up_array is not None:
        for index, cu_up in enumerate(cu_up_array):
            error_message, _ = _stop_stub(
                stub=cu_up,
                name=f"CU-UP_{index+1}",
                retina_data=retina_data,
                timeout=gnb_stop_timeout,
                log_search=log_search,
                warning_as_errors=warning_as_errors,
            )
            error_msg_array.append(error_message)

    if cu_cp_array is not None:
        for index, cu_cp in enumerate(cu_cp_array):
            error_message, _ = _stop_stub(
                stub=cu_cp,
                name=f"CU-CP_{index+1}",
                retina_data=retina_data,
                timeout=gnb_stop_timeout,
                log_search=log_search,
                warning_as_errors=warning_as_errors,
            )
            error_msg_array.append(error_message)

    if fivegc_array is not None:
        for index, fivegc in enumerate(fivegc_array):
            error_message, _ = _stop_stub(
                stub=fivegc,
                name=f"5GC {index+1}",
                retina_data=retina_data,
                timeout=fivegc_stop_timeout,
                log_search=log_search,
                warning_as_errors=False,
            )
            error_msg_array.append(error_message)

    if ric is not None:
        error_message, _ = _stop_stub(
            stub=ric,
            name="RIC",
            retina_data=retina_data,
            timeout=gnb_stop_timeout,
            log_search=log_search,
            warning_as_errors=warning_as_errors,
        )
        error_msg_array.append(error_message)

    if channel_emulator is not None:
        error_message, _ = _stop_stub(
            stub=ric,
            name="CHANNEL_EMULATOR",
            retina_data=retina_data,
            timeout=gnb_stop_timeout,
            log_search=log_search,
            warning_as_errors=warning_as_errors,
        )
        error_msg_array.append(error_message)

    # Fail if stop errors
    error_msg_array = list(filter(bool, error_msg_array))
    if error_msg_array:
        pytest.fail(
            f"Stop stage. {error_msg_array[0]}"
            + (("\nFull list of errors:\n - " + "\n - ".join(error_msg_array)) if len(error_msg_array) > 1 else "")
        )

    # Metrics after Stop
    metrics_msg_array = []
    for index, ue_stub in enumerate(ue_array):
        metrics_msg_array.append(_get_metrics_msg(stub=ue_stub, name=f"UE_{index+1}", fail_if_kos=fail_if_kos))
    if gnb_array is not None:
        for index, gnb in enumerate(gnb_array):
            metrics_msg_array.append(_get_metrics_msg(stub=gnb, name=f"GNB_{index+1}", fail_if_kos=fail_if_kos))
    if fivegc_array is not None:
        for fivegc in fivegc_array:
            metrics_msg_array.append(_get_metrics_msg(stub=fivegc, name=f"5GC_{index+1}", fail_if_kos=fail_if_kos))

    # Fail if metric errors
    metrics_msg_array = list(filter(bool, metrics_msg_array))
    if metrics_msg_array:
        pytest.fail(
            f"Metrics validation. {metrics_msg_array[0]}"
            + (("\nFull list of errors:\n - " + "\n - ".join(metrics_msg_array)) if len(metrics_msg_array) > 1 else "")
        )


def ue_stop(
    *,  # This enforces keyword-only arguments
    ue_array: Sequence[UEStub],
    retina_data: RetinaTestData,
    ue_stop_timeout: int = 0,  # Auto
    log_search: bool = True,
    warning_as_errors: bool = True,
):
    """
    Stop an array of UEs to detach from already running gnb and 5gc
    """
    error_msg_array = []
    for index, ue_stub in enumerate(ue_array):
        error_message, _ = _stop_stub(
            stub=ue_stub,
            name=f"UE_{index+1}",
            retina_data=retina_data,
            timeout=ue_stop_timeout,
            log_search=log_search,
            warning_as_errors=warning_as_errors,
        )
        error_msg_array.append(error_message)
    error_msg_array = list(filter(bool, error_msg_array))
    if error_msg_array:
        pytest.fail(
            f"UE Stop. {error_msg_array[0]}"
            + (("\nFull list of errors:\n - " + "\n - ".join(error_msg_array)) if len(error_msg_array) > 1 else "")
        )


def _stop_stub(
    *,  # This enforces keyword-only arguments
    stub: RanStub,
    name: str,
    retina_data: RetinaTestData,
    timeout: int = 0,
    log_search: bool = True,
    warning_as_errors: bool = True,
) -> Tuple[str, int]:
    """
    Stop a stub in the defined timeout (0=auto).
    It uses retina_data to save artifacts in case of failure
    """

    error_msg = ""
    error_count = 0

    with suppress(grpc.RpcError):
        stop_info: StopResponse = stub.Stop(UInt32Value(value=timeout))

        if stop_info.exit_code:
            retina_data.download_artifacts = True
            error_msg = (
                f"{name} crashed with exit code {stop_info.exit_code} ({exit_code_to_message(stop_info.exit_code)}). "
            )

        if log_search:
            log_msg = f"{name} has {stop_info.error_count} errors and {stop_info.warning_count} warnings. "
            if stop_info.error_count:
                log_msg += f"First error is: {stop_info.error_msg}"
            elif stop_info.warning_count:
                log_msg += f"First warning is: {stop_info.warning_msg}"

            if stop_info.error_count or (warning_as_errors and stop_info.warning_count):
                retina_data.download_artifacts = True
                error_msg += log_msg
            elif not warning_as_errors and stop_info.warning_count:
                logging.warning(log_msg)

        if error_msg:
            logging.error(error_msg)
        else:
            logging.info("%s has stopped", name)

        error_count += stop_info.error_count
        if warning_as_errors:
            error_count += stop_info.warning_count

    return error_msg, error_count


def _get_metrics_msg(
    *, stub: RanStub, name: str, fail_if_kos: bool = False  # The "*" enforces keyword-only arguments
) -> str:
    if fail_if_kos:
        with suppress(grpc.RpcError):
            metrics: Metrics = stub.GetMetrics(Empty())
            nof_kos = metrics.aggregate.nof_ko_dl + metrics.aggregate.nof_ko_ul
            if nof_kos and fail_if_kos:
                return f"{name} has {nof_kos} KOs / retrxs"
    return ""
