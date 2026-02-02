#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Amarisoft UE Agent
"""

import ipaddress
import json
import logging
import math
import os
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from time import sleep
from typing import Dict, Generator, Optional, Tuple

import grpc
import websocket
from google.protobuf.empty_pb2 import Empty
from google.protobuf.text_format import MessageToString
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.wrappers_pb2 import Int32Value, UInt32Value
from retina.protocol.base_pb2 import Metrics, StopResponse, UEDefinition, UeMetrics
from retina.protocol.ue_pb2 import HandoverInfo, Position, ReestablishmentInfo, RrcMessages, UEAttachedInfo, UEStartInfo

from retina.agent.drivers.amarisoft_ws import AmarisoftBaseDriver, AmarisoftWebSocket
from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.ue import SubscriberWithStatus, UEDriver
from retina.agent.features.executor import LocalExecutor, SshExecutor
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import template_defaults, testbed_defaults, ue_defaults
from retina.agent.templates import template_path
from retina.agent.tools.time import TimeoutHandler


# pylint: disable=too-many-instance-attributes
@dataclass
class _CellInfo:
    rf_port: int
    band: int
    bandwidth: int
    dl_nr_arfcn: int
    ssb_nr_arfcn: int
    subcarrier_spacing: int
    ssb_subcarrier_spacing: int
    position: Position = 0
    pdcch_log_filename: str = ""


@dataclass
class _RFSplit72Info:
    interface: str = ""
    du_mac_addr: str = ""


# pylint: disable=too-many-instance-attributes
class AmarisoftUe(UEDriver, AmarisoftBaseDriver):
    """
    Amarisoft UE Agent
    """

    AMARISOFT_LICENSE_RETRY: float = 3
    AMARISOFT_STDOUT_NAME: str = "stdout"
    AMARISOFT_LOG_FILENAME: str = "ue.log"
    AMARISOFT_CONF_FILE_BASE_NAME: str = "amarisoft_ue_base.cfg"
    AMARISOFT_CONF_FILE_DATA_NAME: str = "amarisoft_ue_data.cfg"
    AMARISOFT_CONF_FILE_FINAL_NAME: str = "amarisoft_ue.cfg"
    AMARISOFT_START_UP_TIMEOUT: int = 5
    AMARISOFT_POWER_ON_SLEEP: float = 0.3
    AMARISOFT_STOP_TIMEOUT: int = 64
    AMARISOFT_WAIT_BEFORE_STOP: int = 3
    AMARISOFT_VERSION_REGEX: str = r"UE version (.*), Copyright"
    AMARISOFT_UE_INFO_WAIT: float = 0.6
    AMARISOFT_ATTACH_WAIT: float = 4
    AMARISOFT_WAIT_BETWEEN_TRAFFIC_AND_STOP: int = 20
    _METRICS_ENCODING: str = "utf-8"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._5gc_mask: int
        # Dict of subscriber for each client
        self._subscriber_client_dict: Dict[str, SubscriberWithStatus] = {}
        self._subscriber_count: int = 0
        self._amarisoft_lock: Lock = Lock()
        self._metrics_lock: Lock = Lock()
        self._metrics_dict: Dict[str, Dict[int, UeMetrics]] = {}

    def _get_binary_name(self) -> str:
        return "lteue"

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> UEDefinition:
        ue_definition: UEDefinition = super().GetDefinition(request, context)

        if ue_defaults.ue_simulator_mode:
            return ue_definition

        if context.peer() not in self._subscriber_client_dict:
            # New subscriber
            with self._amarisoft_lock:
                self._subscriber_count += 1

                # Change the imsi by adding the internal subscriber_id
                # so each connection has a different subscriber
                ue_definition.subscriber.imsi = str(int(ue_definition.subscriber.imsi) + self._subscriber_count).zfill(
                    len(ue_definition.subscriber.imsi)
                )
                ue_definition.subscriber.tel = ue_definition.subscriber.tel + self._subscriber_count
                if len(ue_defaults.ue_sds) >= self._subscriber_count:
                    ue_definition.subscriber.sd = ue_defaults.ue_sds[self._subscriber_count - 1]

                # Add to the dictionary: peer - subscriber(+status)
                self._subscriber_client_dict[context.peer()] = SubscriberWithStatus(
                    ue_definition.subscriber, self._subscriber_count
                )
        else:
            # Existing subscriber. Reuse imsi
            ue_definition.subscriber.imsi = self._subscriber_client_dict[context.peer()].subscriber.imsi
            ue_definition.subscriber.tel = self._subscriber_client_dict[context.peer()].subscriber.tel
            ue_definition.subscriber.sd = self._subscriber_client_dict[context.peer()].subscriber.sd

        return ue_definition

    @property
    def _any_virtual_ue_already_started(self) -> bool:
        return any(
            map(
                lambda sub_with_status: sub_with_status.started,
                self._subscriber_client_dict.values(),
            )
        )

    def Start(self, request: UEStartInfo, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            if len(request.du_definition) > 1 and ue_defaults.num_cells * max(
                ue_defaults.nof_antennas_dl, ue_defaults.nof_antennas_ul
            ) > len(request.du_definition):
                logging.warning(
                    "Number of cells (%d) and antennas (%d) exceeds the number of DU definitions (%d)",
                    ue_defaults.num_cells,
                    max(ue_defaults.nof_antennas_dl, ue_defaults.nof_antennas_ul),
                    len(request.du_definition),
                )
                raise ValueError(
                    f"Number of cells ({ue_defaults.num_cells}) and antennas "
                    f"({max(ue_defaults.nof_antennas_dl, ue_defaults.nof_antennas_ul)}) "
                    f"exceeds the number of DU definitions ({len(request.du_definition)})"
                )

            with self._amarisoft_lock:
                return self._start_unlock(request, context)

    # pylint: disable=too-many-branches
    def _start_unlock(self, request: UEStartInfo, context: grpc.ServicerContext) -> Empty:
        if not self._any_virtual_ue_already_started:
            self._stop_unlock(UInt32Value(value=request.start_info.timeout), context.peer())

            self._5gc_mask = request.fivegc_definition.tun_mask

            if testbed_defaults.type == "ru":
                if len(testbed_defaults.ru_network_interface) != len(testbed_defaults.ru_du_mac_addr):
                    logging.warning(
                        "Incorrect split 7.2 request: RU properties in the testbed should have the same size"
                    )
                    raise ValueError(
                        "The UE agent can't be started in split 7.2 mode due to incorrect testbed parameters"
                    )

                if ue_defaults.num_cells > len(testbed_defaults.ru_network_interface):
                    logging.warning(
                        "Incorrect split 7.2 config: %s cells are requested while "
                        "%s network interfaces are supported by the testbed",
                        ue_defaults.num_cells,
                        len(testbed_defaults.ru_network_interface),
                    )
                    raise ValueError("The UE agent can't be started in split 7.2 mode due to incorrect config")

            config_file = self._render(
                filename=self.AMARISOFT_CONF_FILE_FINAL_NAME,
                templates={
                    self.AMARISOFT_CONF_FILE_BASE_NAME: template_defaults.main,
                    self.AMARISOFT_CONF_FILE_DATA_NAME: template_defaults.ue,
                },
                prefix="{",
                suffix="\n}",
                values={
                    **get_module_variables(testbed_defaults),
                    **get_module_variables(ue_defaults),
                    # Logging
                    **self._get_log_variables(ue_defaults.log_level, self.AMARISOFT_LOG_FILENAME),
                    # RF drivers
                    "zmq_def": (
                        (
                            f"tcp://*:{testbed_defaults.port_array[i]}",
                            f"tcp://{request.du_definition[i if len(request.du_definition) > 1 else 0].zmq_ip}:"
                            + str(
                                request.du_definition[i if len(request.du_definition) > 1 else 0].zmq_port_array[
                                    i if len(request.du_definition) == 1 else 0
                                ]
                            ),
                        )
                        for i in range(
                            ue_defaults.num_cells * max(ue_defaults.nof_antennas_dl, ue_defaults.nof_antennas_ul)
                        )
                    ),
                    "s72_def": tuple(
                        _RFSplit72Info(
                            interface=testbed_defaults.ru_network_interface[i],
                            du_mac_addr=testbed_defaults.ru_du_mac_addr[i],
                        )
                        for i in range(ue_defaults.num_cells if testbed_defaults.type == "ru" else 0)
                    ),
                    "prach_ports": str(list(range(4, 4 + ue_defaults.nof_antennas_ul))),
                    "sdr_driver_args": f"type={testbed_defaults.model}," f"{testbed_defaults.args}",
                    "tx_gain": testbed_defaults.tx_gain if ue_defaults.tx_gain < 0 else ue_defaults.tx_gain,
                    "rx_gain": testbed_defaults.rx_gain if ue_defaults.rx_gain < 0 else ue_defaults.rx_gain,
                    # Cell
                    "sample_rate": (
                        testbed_defaults.sample_rate if ue_defaults.sample_rate < 0 else ue_defaults.sample_rate
                    ),
                    "cell_array": tuple(
                        _CellInfo(
                            rf_port=i,
                            band=ue_defaults.cells[i]["band"] if ue_defaults.cells else -1,
                            bandwidth=ue_defaults.cells[i]["bandwidth"] if ue_defaults.cells else -1,
                            dl_nr_arfcn=ue_defaults.cells[i]["dl_nr_arfcn"] if ue_defaults.cells else -1,
                            ssb_nr_arfcn=ue_defaults.cells[i]["ssb_nr_arfcn"] if ue_defaults.cells else -1,
                            subcarrier_spacing=(
                                ue_defaults.cells[i]["subcarrier_spacing"] if ue_defaults.cells else -1
                            ),
                            ssb_subcarrier_spacing=(
                                ue_defaults.cells[i]["ssb_subcarrier_spacing"] if ue_defaults.cells else -1
                            ),
                            position=Position(
                                x=i * ue_defaults.cell_position_offset[0],
                                y=i * ue_defaults.cell_position_offset[1],
                                z=i * ue_defaults.cell_position_offset[2],
                            ),
                            pdcch_log_filename=(
                                self.get_filepath_in_report_folder(f"ue_pdcch_{i}.log") if ue_defaults.pdcch_log else ""
                            ),
                        )
                        for i in range(ue_defaults.num_cells)
                    ),
                    # UE List
                    "ue_count": len(self._subscriber_client_dict),
                    "subscriber_array": tuple(
                        map(
                            lambda item: item.subscriber,
                            sorted(
                                self._subscriber_client_dict.values(),
                                key=lambda item: item.subscriber_id,
                            ),
                        )
                    ),
                },
            )

            logfile = self.get_filepath_in_report_folder(self.AMARISOFT_STDOUT_NAME + ".log")
            self._last_log_array = (logfile,)

            timeout_handler = TimeoutHandler(
                request.start_info.timeout if request.start_info.timeout else self.AMARISOFT_START_UP_TIMEOUT,
                msg="Amarisoft lteue start timeout reached",
            )

            # Add -t flag for ZMQ mode to use radio-derived clock
            zmq_args = ["-t"] if testbed_defaults.type == "zmq" else []

            # Launch
            self.start_sut(
                *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
                self._get_binary_name(),
                *zmq_args,
                config_file,
                *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
                logfile=logfile,
                dryrun=request.start_info.dryrun,
            )

            if not request.start_info.dryrun:
                if not self._is_license_available(timeout_handler):
                    request.start_info.timeout = int(timeout_handler.get_remaining_timeout())
                    return self._start_unlock(request, context)
            try:
                self._websocket = AmarisoftWebSocket()
            except (ConnectionRefusedError, ConnectionResetError) as err:
                raise ChildProcessError("Process has died") from err

            self._metrics_dict.clear()

            with suppress(BrokenPipeError, AttributeError):
                # Enter (stop previous command) + t
                self._process.stdin.write("\nt\n")
                self._process.stdin.flush()

            while timeout_handler.not_reached():
                cells: Dict = self._websocket.send_command_and_wait_response(message="config_get").get("cells", {})
                if all("pci" in cell_info for cell_info in cells.values()):
                    break
                sleep(self.AMARISOFT_POWER_ON_SLEEP)

        if self._websocket is None:
            raise ChildProcessError("Process has died")

        if len(self._subscriber_client_dict) > 0:
            subscriber_id = self._subscriber_client_dict[context.peer()].subscriber_id
            self._websocket.send_command_and_wait_response(message="power_on", ue_id=subscriber_id)
            sleep(self.AMARISOFT_POWER_ON_SLEEP)
            self._subscriber_client_dict[context.peer()].started = True
            logging.info("Power on user with id %s", subscriber_id)
        else:
            logging.info("Test Simulation Mode")

        self._metrics_dict[context.peer()] = {}

        if not self._check_alive_thread.is_alive():
            raise ChildProcessError("Process has died")

        return Empty()

    # pylint: disable=inconsistent-return-statements
    def WaitUntilAttached(self, request: UInt32Value, context: grpc.ServicerContext) -> UEAttachedInfo:
        with notify_grpc_exception(context):
            for ue_info in self._ue_get(
                context_peer=context.peer(),
                update=False,
                timeout=request.value,
                interval=self.AMARISOFT_UE_INFO_WAIT,
            ):
                for apn in ue_info.get("pdn_list", []):
                    if apn.get("apn", "").startswith(ue_defaults.apn):
                        ipv4 = apn["ipv4"]
                        logging.info(
                            "Attached user with id %s (msg id %s)",
                            self._subscriber_client_dict[context.peer()].subscriber_id,
                            ue_info["message_id"],
                        )
                        sleep(self.AMARISOFT_ATTACH_WAIT)
                        return UEAttachedInfo(
                            ipv4=ipv4,
                            ipv4_gateway=str(
                                ipaddress.ip_network(f"{ipv4}/{self._5gc_mask}", False).network_address + 1
                            ),
                            rnti=int(ue_info["rnti"]),
                            ue_id=int(ue_info["ue_id"]),
                        )

    def WaitUntilReleased(self, request: UInt32Value, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            for ue_info in self._ue_get(
                context_peer=context.peer(),
                update=False,
                timeout=request.value,
                interval=self.AMARISOFT_UE_INFO_WAIT,
            ):
                if ue_info.get("rrc_state") == "idle":
                    logging.info(
                        "Released user with id %s (msg id %s)",
                        self._subscriber_client_dict[context.peer()].subscriber_id,
                        ue_info["message_id"],
                    )
                    break
        return Empty()

    def GetMessages(self, request: Empty, context: grpc.ServicerContext) -> RrcMessages:
        logging.info("Querying message counters")
        if self._websocket is None:
            raise ChildProcessError("Process has died")

        for ue_info in self._ue_get(
            context_peer=context.peer(),
            update=False,
            timeout=self.AMARISOFT_WAIT_BEFORE_STOP,
        ):
            return self._parse_messages(ue_info["counters"]["messages"])

    def _parse_messages(self, messages: Dict) -> RrcMessages:
        return RrcMessages(
            nof_setup=messages.get("nr_rrc_setup", 0),
            nof_reestablishment_complete=messages.get("nr_rrc_reestablishment_complete", 0),
            nof_reconfiguration=messages.get("nr_rrc_reconfiguration", 0),
            nof_reconfiguration_complete=messages.get("nr_rrc_reconfiguration_complete", 0),
        )

    def Reestablishment(self, request: UInt32Value, context: grpc.ServicerContext) -> ReestablishmentInfo:
        with notify_grpc_exception(context):
            subscriber_id = self._subscriber_client_dict[context.peer()].subscriber_id

            if self._websocket is None:
                raise ChildProcessError("Process has died")

            logging.info("Starting reestablishment for UE %s", subscriber_id)

            # Get current number of reestablishments
            for ue_info in self._ue_get(
                context_peer=context.peer(),
                update=False,
                timeout=self.AMARISOFT_WAIT_BEFORE_STOP,
            ):
                old_messages = self._parse_messages(ue_info["counters"]["messages"])
                break

            # Launch reestablishment
            self._websocket.send_command_and_wait_response(message="rrc_reest", ue_id=subscriber_id)

            # Wait until reestablishment completed
            for ue_info in self._ue_get(
                context_peer=context.peer(),
                update=True,
                timeout=request.value,
                timeout_msg=f"Timeout reached. UE {subscriber_id} didn't accomplish the reestablishment.",
            ):
                new_messages = self._parse_messages(ue_info["counters"]["messages"])

                if (
                    new_messages.nof_reestablishment_complete > old_messages.nof_reestablishment_complete
                    and ue_info.get("emm_state", "") == "registered"
                ):
                    logging.info("Reestablishment for UE %s finished (msg id %s)", subscriber_id, ue_info["message_id"])
                    return ReestablishmentInfo(
                        status=new_messages.nof_setup == old_messages.nof_setup,
                        previous_messages=old_messages,
                        last_messages=new_messages,
                    )

        return ReestablishmentInfo(status=False)

    def Move(self, request: Position, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            subscriber_id = self._subscriber_client_dict[context.peer()].subscriber_id

            if self._websocket is None:
                raise ChildProcessError("Process has died")

            logging.info("Starting movement for UE %s", subscriber_id)

            self._websocket.send_command_and_wait_response(
                message="ue_move", ue_id=subscriber_id, position=[request.x, request.y, request.z]
            )

            # Validate action
            for ue_info in self._ue_get(
                context_peer=context.peer(),
                update=False,
                timeout=self.AMARISOFT_WAIT_BEFORE_STOP,
            ):
                if ue_info.get("position", []) == [request.x, request.y, request.z]:
                    logging.info("Move UE %s finished (msg id %s)", subscriber_id, ue_info["message_id"])
                    break

            return Empty()

    # pylint: disable=too-many-locals
    def ExpectHandover(self, request: UInt32Value, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            subscriber_id = self._subscriber_client_dict[context.peer()].subscriber_id

            if self._websocket is None:
                raise ChildProcessError("Process has died")

            logging.info("Waiting for the UE %s to handover", subscriber_id)

            # Get current number of rrc_reconfiguration
            for ue_info in self._ue_get(
                context_peer=context.peer(),
                update=False,
                timeout=self.AMARISOFT_WAIT_BEFORE_STOP,
            ):
                old_messages = self._parse_messages(ue_info["counters"]["messages"])
                break

            # Get current pci
            old_cell_pci = tuple(
                sorted(self._metrics_dict[context.peer()].values(), key=lambda ue_info: ue_info.time_last.ToDatetime())
            )[-1].pci

            # Wait until HO completed
            timeout_msg = f"Timeout reached. UE {subscriber_id} is still connected to cell pci={old_cell_pci}"
            timeout_handler = TimeoutHandler(request.value, msg=timeout_msg)
            while timeout_handler.not_reached():
                for ue_info in self._ue_get(
                    context_peer=context.peer(),
                    update=True,
                    timeout=timeout_handler.get_remaining_timeout(),
                    timeout_msg=timeout_msg,
                ):
                    new_messages = self._parse_messages(ue_info["counters"]["messages"])
                    diff_nof_reconfiguration = new_messages.nof_reconfiguration - old_messages.nof_reconfiguration
                    diff_nof_reconfiguration_complete = (
                        new_messages.nof_reconfiguration_complete - old_messages.nof_reconfiguration_complete
                    )
                    new_cell_pci = tuple(
                        sorted(
                            self._metrics_dict[context.peer()].values(),
                            key=lambda ue_info: ue_info.time_last.ToDatetime(),
                        )
                    )[-1].pci

                    # Validation
                    if new_cell_pci != old_cell_pci:
                        if (
                            (new_messages.nof_setup > old_messages.nof_setup)
                            or (new_messages.nof_reestablishment_complete > old_messages.nof_reestablishment_complete)
                            or (diff_nof_reconfiguration == 0)
                            or (diff_nof_reconfiguration != diff_nof_reconfiguration_complete)
                        ):
                            logging.error(
                                "UE %s forced to either reestablish or start a completely new connection. "
                                "Cell pci=%s -> Cell pci=%s (msg id %s)",
                                subscriber_id,
                                old_cell_pci,
                                new_cell_pci,
                                ue_info["message_id"],
                            )
                            return HandoverInfo(
                                status=False,
                                previous_pci=old_cell_pci,
                                last_pci=new_cell_pci,
                                previous_messages=old_messages,
                                last_messages=new_messages,
                            )
                        with self._metrics_lock:
                            for cell_info in ue_info["cells"]:
                                ue_metric = self._metrics_dict[context.peer()][cell_info["pci"]]
                                ue_metric.nof_handovers += 1
                        logging.info(
                            "UE %s successfully HO from cell pci=%s to cell pci=%s (msg id %s)",
                            subscriber_id,
                            old_cell_pci,
                            new_cell_pci,
                            ue_info["message_id"],
                        )
                        return HandoverInfo(
                            status=True,
                            previous_pci=old_cell_pci,
                            last_pci=new_cell_pci,
                            previous_messages=old_messages,
                            last_messages=new_messages,
                        )
        return HandoverInfo(status=False)

    def Stop(self, request: UInt32Value, context: Optional[grpc.ServicerContext]) -> StopResponse:
        with self._amarisoft_lock:
            response = self._stop_unlock(request, context.peer() if context is not None else "unknown")
            if response is not None:
                return response
            return super().Stop(request, context)

    # pylint: disable=too-many-branches
    def _stop_unlock(self, request: UInt32Value, context_peer: str) -> Optional[StopResponse]:

        if self._any_virtual_ue_already_started and context_peer in self._subscriber_client_dict:
            subscriber_id = self._subscriber_client_dict[context_peer].subscriber_id

            if not self._subscriber_client_dict[context_peer].started:
                # Already stopped
                logging.info("UE %s already stopped", subscriber_id)
                return StopResponse()

            try:
                if self._websocket is None:
                    raise ChildProcessError("Process has died")
                try:
                    time_spend_after_traffic = (datetime.now() - self._last_traffic_timestamp).total_seconds()
                    if time_spend_after_traffic < self.AMARISOFT_WAIT_BETWEEN_TRAFFIC_AND_STOP:
                        logging.info("Waiting for traffic to be scheduled before powering off")
                        sleep(self.AMARISOFT_WAIT_BETWEEN_TRAFFIC_AND_STOP - time_spend_after_traffic)
                    timeout_value = (
                        request.value if request.value > 0 else (self.AMARISOFT_STOP_TIMEOUT / self._subscriber_count)
                    )
                    logging.info("Stopping UE %s with timeout %s seconds", subscriber_id, timeout_value)
                    timeout_handler = TimeoutHandler(timeout_value)
                    self._validate_state(
                        context_peer=context_peer,
                        cmd="deregister",
                        field="rrc_state",
                        state_list=("idle",),
                        timeout=timeout_handler.get_remaining_timeout(),
                    )
                    self._validate_state(
                        context_peer=context_peer,
                        cmd="power_off",
                        field="emm_state",
                        state_list=("power off",),
                        timeout=timeout_handler.get_remaining_timeout(),
                    )
                except TimeoutError:
                    # We send a final power_off
                    logging.warning("Timeout reached while trying to stop UE %s in a safe way", subscriber_id)
                    self._websocket.send_command_and_wait_response(message="power_off", ue_id=subscriber_id)
                    # Last status query to save metrics
                    for _ in self._ue_get(
                        context_peer=context_peer,
                        update=False,
                        timeout=self.AMARISOFT_STOP_TIMEOUT,
                    ):
                        break

            except (ChildProcessError, websocket.WebSocketConnectionClosedException):
                logging.warning("Can not stop UE %s in a safe way due to a process error", subscriber_id)

            self._subscriber_client_dict[context_peer].started = False
            logging.info("Power off UE id %s", subscriber_id)

            # After power off this virtualUE, there are still some active virtual UEs,
            # so we can't call real Stop, just return success
            if self._any_virtual_ue_already_started:
                return StopResponse()
            self._subscriber_client_dict.clear()
            self._subscriber_count = 0

        elif self._any_virtual_ue_already_started and context_peer not in self._subscriber_client_dict:
            # There are virtual UEs started BUT the client that request the stop is UNKNOWN
            # Causes:
            #  1 - Virtual UEs not stopped in the test and this is final Stop called by agent itself
            #  2 - Unknown client
            # Then we need to power_off all virtualUEs and stop everything
            logging.warning("Unknown client [%s]. Stopping all virtual UEs", context_peer)

            for (
                active_context_peer,
                sub_with_status,
            ) in self._subscriber_client_dict.items():
                if sub_with_status.started:
                    self._stop_unlock(request, active_context_peer)
            return None

        # No pending virtual UEs to stop or sut already stopped
        if self._process is not None and self._websocket is not None:
            sleep(self.AMARISOFT_WAIT_BEFORE_STOP)
            self._websocket.quit()
            # Close metrics file
            with open(
                self.get_filepath_in_report_folder(ue_defaults.metrics_filename_json),
                "a+",
                encoding=self._METRICS_ENCODING,
            ) as fd:
                if fd.tell() > 0:
                    fd.write("]")
        return None

    def _validate_state(
        self,
        *,
        context_peer: str,
        cmd: str,
        field: str,
        state_list: Tuple[str, ...],
        timeout: int = AMARISOFT_STOP_TIMEOUT,
    ):  # pylint: disable=too-many-arguments
        subscriber_id = self._subscriber_client_dict[context_peer].subscriber_id

        if self._websocket is None:
            raise ChildProcessError("Process has died")

        # Run command
        self._websocket.send_command_and_wait_response(message=cmd, ue_id=subscriber_id)

        # Query ue status with timeout
        for ue_info in self._ue_get(
            context_peer=context_peer,
            update=True,
            timeout=timeout,
        ):
            if ue_info.get(field, "") in state_list:
                return

    def _stop_binary(self, stop_timeout: int = 0) -> Int32Value:
        process_running = self._process is not None and self._process.is_running()
        if process_running:
            sleep(self.AMARISOFT_WAIT_BEFORE_STOP)
        stop_info = super()._stop_binary(stop_timeout)
        # Clean binary generated files from report folder
        if process_running:
            for path_object in self.get_current_report_folder().rglob("*"):
                if path_object.is_file() and path_object.suffix == ".bin":
                    path_object.unlink()
        return stop_info

    @property
    def _warning_regex(self) -> str:
        return r"^.*warning(?!.*unused property).*$"

    @property
    def _error_regex(self) -> str:
        return r"^.*error.*$"

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _ue_get(
        self,
        *,
        context_peer: str,
        update: bool,
        timeout: Optional[float] = -1,
        interval: float = 0,
        timeout_msg: str = "Timeout reached",
    ) -> Generator[Dict, None, None]:
        # Query ue status with timeout
        subscriber_id = self._subscriber_client_dict[context_peer].subscriber_id
        timeout_handler = TimeoutHandler(timeout, msg=timeout_msg)
        while True:
            if self._websocket is None:
                raise ChildProcessError("Process has died")
            if update:
                response = self._websocket.send_command_and_wait_response(
                    message="ue_get",
                    ue_id=subscriber_id,
                    update=True,
                    timeout=math.ceil(timeout_handler.get_remaining_timeout()),
                )
            else:
                sleep(interval)
                response = self._websocket.send_command_and_wait_response(
                    message="ue_get",
                    ue_id=subscriber_id,
                )

            with self._metrics_lock:
                # Save metrics into file
                with open(
                    self.get_filepath_in_report_folder(ue_defaults.metrics_filename_json),
                    "a+",
                    encoding=self._METRICS_ENCODING,
                ) as fd:
                    # Save to file
                    if fd.tell() == 0:
                        # First line
                        fd.write("[")
                        fd.flush()
                    else:
                        fd.write("," + os.linesep)
                    fd.write(json.dumps(response))

                # Save metrics from ue_get
                self._parse_metrics(context_peer, response)

            for ue_info in response["ue_list"]:
                if ue_info["ue_id"] == subscriber_id:
                    yield {**ue_info, "message_id": response["message_id"]}

            if update:
                try:
                    timeout_handler.not_reached()
                except TimeoutError:
                    # When timeout is reached for a ue_get+update operation
                    # Let's do a final extra request with ue_get+update
                    update = False
                    continue

            timeout_handler.not_reached()

    def _parse_metrics(self, context_peer: str, metric_info: Dict):
        timestamp = Timestamp()
        timestamp.FromNanoseconds(int(metric_info["utc"] * 1e9))
        for ue_info in metric_info["ue_list"]:
            for cell_info in ue_info["cells"]:
                if cell_info["pci"] not in self._metrics_dict[context_peer]:
                    self._metrics_dict[context_peer][cell_info["pci"]] = UeMetrics(
                        pci=cell_info["pci"],
                        rnti=ue_info.get("rnti", 0),
                        dl_nof_ok=ue_info["dl_rx_count"],
                        dl_nof_ko=ue_info["dl_err_count"] + ue_info["dl_retx_count"],
                        dl_bitrate=ue_info["dl_bitrate"],
                        dl_bitrate_min=ue_info["dl_bitrate"],
                        dl_bitrate_max=ue_info["dl_bitrate"],
                        ul_nof_ok=ue_info["ul_tx_count"],
                        ul_nof_ko=ue_info["ul_retx_count"],
                        ul_bitrate=ue_info["ul_bitrate"],
                        ul_bitrate_min=ue_info["ul_bitrate"],
                        ul_bitrate_max=ue_info["ul_bitrate"],
                        nof_reestablishments=ue_info["counters"]["messages"].get("nr_rrc_reestablishment_complete", 0),
                        time_first=Timestamp(seconds=timestamp.seconds, nanos=timestamp.nanos),
                        time_last=Timestamp(seconds=timestamp.seconds, nanos=timestamp.nanos),
                    )
                else:
                    ue_metric = self._metrics_dict[context_peer][cell_info["pci"]]

                    ue_metric.dl_nof_ok += ue_info["dl_rx_count"]
                    ue_metric.dl_nof_ko += ue_info["dl_err_count"] + ue_info["dl_retx_count"]

                    ue_metric.ul_nof_ok += ue_info["ul_tx_count"]
                    ue_metric.ul_nof_ko += ue_info["ul_retx_count"]

                    ue_metric.dl_bitrate_min = min(ue_metric.dl_bitrate_min, ue_info["dl_bitrate"])
                    ue_metric.dl_bitrate_max = max(ue_metric.dl_bitrate_max, ue_info["dl_bitrate"])

                    ue_metric.ul_bitrate_min = min(ue_metric.ul_bitrate_min, ue_info["ul_bitrate"])
                    ue_metric.ul_bitrate_max = max(ue_metric.ul_bitrate_max, ue_info["ul_bitrate"])

                    t_old = (ue_metric.time_last.ToDatetime() - ue_metric.time_first.ToDatetime()).total_seconds()
                    t_new = (timestamp.ToDatetime() - ue_metric.time_last.ToDatetime()).total_seconds()
                    t_beginning = (timestamp.ToDatetime() - ue_metric.time_first.ToDatetime()).total_seconds()

                    if t_beginning:
                        ue_metric.dl_bitrate = (
                            (ue_metric.dl_bitrate * t_old) + (ue_info["dl_bitrate"] * t_new)
                        ) / t_beginning
                        ue_metric.ul_bitrate = (
                            (ue_metric.ul_bitrate * t_old) + (ue_info["ul_bitrate"] * t_new)
                        ) / t_beginning

                    ue_metric.time_last.seconds = timestamp.seconds
                    ue_metric.time_last.nanos = timestamp.nanos

                    ue_metric.nof_reestablishments = ue_info["counters"]["messages"].get(
                        "nr_rrc_reestablishment_complete", 0
                    )

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        metrics = super().GetMetrics(request, context)
        if context.peer() in self._metrics_dict:
            metrics.ue_array.extend(self._metrics_dict[context.peer()].values())
        else:
            metrics.ue_array.extend(
                (ue_metric for ue_dict in self._metrics_dict.values() for ue_metric in ue_dict.values())
            )
        if len(metrics.ue_array) == 1:
            metrics.total.CopyFrom(metrics.ue_array[0])
            metrics.total.pci = 0
            metrics.total.rnti = 0
        logging.info("Metrics: %s", MessageToString(metrics, as_one_line=True))
        return metrics


class LocalAmarisoftUe(AmarisoftUe):
    """
    Amarisoft UE Agent for local execution
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())


class RemoteAmarisoftUe(AmarisoftUe):
    """
    Amarisoft UE Agent for remote execution
    """

    _ZMQ_DRIVER = "trx_ocudu.so"
    _NETNS_TUN_SH = "amarisoft_ue_tun_netns.sh"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=SshExecutor())

    def _get_sut_version(self) -> str:
        return ""

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> UEDefinition:
        testbed_defaults.ip_zmq = testbed_defaults.api_address
        return super().GetDefinition(request, context)

    def _start_unlock(self, request: UEStartInfo, context: grpc.ServicerContext) -> Empty:
        if not self._any_virtual_ue_already_started:
            remote_tun_sh = str(self._get_amarisoft_folder().joinpath(self._NETNS_TUN_SH))
            self._executor.copy_file(template_path(self._NETNS_TUN_SH), remote_tun_sh)
            ue_defaults.tun_sh_path = remote_tun_sh
        return super()._start_unlock(request, context)

    def start_sut(self, *args, **kwargs) -> None:
        if testbed_defaults.type == "zmq":
            zmq_driver_path = str(self._get_amarisoft_folder().joinpath(self._ZMQ_DRIVER))
            self._executor.copy_file(zmq_driver_path, zmq_driver_path)
        self._kill_existing_lte()
        return super().start_sut(*args, **kwargs)

    def _get_iperf_binary(self, context: grpc.ServicerContext) -> Tuple[str, ...]:
        return ("ip", "netns", "exec", f"ue{self._subscriber_client_dict[context.peer()].subscriber_id}", "iperf3")

    def _get_ping_binary(self, context: grpc.ServicerContext) -> Tuple[str, ...]:
        return ("ip", "netns", "exec", f"ue{self._subscriber_client_dict[context.peer()].subscriber_id}", "ping")
