# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Basic Agent Code
"""

import logging
import os
import platform
import re
import tempfile
import traceback
from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, Generator, Optional, Tuple

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import BytesValue, StringValue, UInt32Value
from jinja2 import Template
from retina.protocol.artifact import archive_artifact_folder, calculate_folder_hash
from retina.protocol.base_pb2 import Metrics, Parameter, PingRequest, PingResponse, RetinaInfo, StopResponse
from retina.protocol.base_pb2_grpc import BaseServicer
from retina.protocol.redact import add_log_secret

import retina.agent
from retina.agent.app.parameter_manager import set_parameter
from retina.agent.app.resource_manager import ResourceManager
from retina.agent.features.executor import Executor
from retina.agent.templates import template_path
from retina.agent.tools.time import now_timestamp_file, now_utc_timestamp

try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version  # type: ignore


class BaseDriver(BaseServicer, metaclass=ABCMeta):
    """
    Basic Agent Code
    """

    RUNTIME_LIBS_FOLDER = "retina-libs"

    PING_PACKET_SENT_REGEX = re.compile(r"([0-9]+) packets transmitted")
    PING_PACKAGE_RECEIVED_REGEX = re.compile(r"([0-9]+)\s+((received)|(packets received))")
    PING_RTT_REGEX = re.compile(
        r"rtt min\/avg\/max\/mdev = " + r"(\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?) ms"
    )

    def __init__(self, *args, executor: Executor, report_folder: str, resource_folder: str, **kwargs) -> None:
        self._executor = executor
        self._current_report_folder: Optional[Path] = None
        self._base_folder: Path = Path(report_folder).resolve()
        self._base_folder.mkdir(parents=True, exist_ok=True)
        self._resource_folder: Path = Path(resource_folder).resolve()
        self._resource_folder.mkdir(parents=True, exist_ok=True)
        self._last_artifact_id = None
        self._shutdown_callback: Optional[Callable] = None
        ResourceManager.load_resources(self._resource_folder)
        self._save_to_testbed()
        super().__init__(*args, **kwargs)

    def set_shutdown_callback(self, callback: Callable) -> None:
        """Add a shutdown callback"""
        self._shutdown_callback = callback

    def _save_to_testbed(self):  # This is temporal, remove it when testbed is removed
        """
        Save the current resources to the testbed.py file.
        This is a temporal method until we remove testbed and use resources only.
        """
        # pylint: disable=too-many-statements,too-many-branches
        available_resources = ResourceManager.get_resources()

        set_parameter("testbed.type", "zmq")
        set_parameter("testbed.ip", available_resources.address)
        set_parameter("testbed.ip_zmq", available_resources.address)

        # Node
        if available_resources.node is not None:
            if available_resources.node.node_ip:
                set_parameter("testbed.ip_zmq", available_resources.node.node_ip)
            if available_resources.node.backhaul_ip:
                set_parameter("testbed.ip", available_resources.node.backhaul_ip)
            if available_resources.node.port_array:
                set_parameter("testbed.port_array", available_resources.node.port_array)
            set_parameter("testbed.lcores_eal_args", available_resources.node.lcores_eal)

        # Remote
        if available_resources.remote is not None:
            set_parameter("testbed.api_address", available_resources.remote.address)
            add_log_secret(available_resources.remote.user)
            set_parameter("testbed.user", available_resources.remote.user)
            add_log_secret(available_resources.remote.password)
            set_parameter("testbed.password", available_resources.remote.password)
            set_parameter("testbed.tma_path", available_resources.remote.path)

        # Core
        if available_resources.core is not None:
            set_parameter("testbed.amf_address", available_resources.core.address)
            set_parameter("testbed.amf_port", available_resources.core.port)
            set_parameter("5gc.tun_subnet", available_resources.core.address)
            set_parameter("5gc.tun_mask", available_resources.core.mask)

        # API
        if available_resources.api is not None:
            set_parameter("testbed.api_address", available_resources.api.address)
            set_parameter("testbed.api_port", available_resources.api.port)

        # License
        if available_resources.license is not None:
            add_log_secret(available_resources.license.address)
            set_parameter("testbed.license_server", available_resources.license.address)
            set_parameter("testbed.license_args", available_resources.license.args)

        # SDR
        if available_resources.sdr is not None:
            set_parameter("testbed.type", "sdr")
            set_parameter("testbed.model", available_resources.sdr.model)
            add_log_secret(available_resources.sdr.args)
            set_parameter("testbed.args", available_resources.sdr.args)
            set_parameter("testbed.sync", available_resources.sdr.sync)
            set_parameter("testbed.sample_rate", available_resources.sdr.sample_rate)
            set_parameter("testbed.tx_gain", available_resources.sdr.tx_gain)
            set_parameter("testbed.rx_gain", available_resources.sdr.rx_gain)

        # RU
        if available_resources.ru is not None:
            set_parameter("testbed.type", "ru")
            set_parameter("testbed.model", available_resources.ru.model)
            set_parameter("testbed.ru_network_interface", available_resources.ru.network_interface)
            set_parameter("testbed.ru_du_mac_addr", available_resources.ru.du_mac_address)
            set_parameter("testbed.ru_ru_mac_addr", available_resources.ru.ru_mac_address)
            set_parameter("testbed.ru_vlan_tag_up", available_resources.ru.vlan_tag_up)
            set_parameter("testbed.ru_vlan_tag_cp", available_resources.ru.vlan_tag_cp)
            set_parameter("testbed.ru_prach_port_id", available_resources.ru.prach_port_id)
            set_parameter("testbed.ru_dl_port_id", available_resources.ru.dl_port_id)
            set_parameter("testbed.ru_ul_port_id", available_resources.ru.ul_port_id)

        # COTS identifier and uSIM params
        if available_resources.ue is not None:
            set_parameter("testbed.type", "android")
            set_parameter("testbed.model", available_resources.ue.model)
            add_log_secret(available_resources.ue.serial_id)
            set_parameter("testbed.serial_id", available_resources.ue.serial_id)
            set_parameter("testbed.imsi", available_resources.ue.imsi)
            set_parameter("testbed.k", available_resources.ue.k)
            set_parameter("testbed.opc", available_resources.ue.opc)
            set_parameter("testbed.amf", available_resources.ue.amf)
            add_log_secret(available_resources.ue.adb_key)
            set_parameter("testbed.adb_key", available_resources.ue.adb_key)

        # Accelerator
        if available_resources.accelerator is not None:
            set_parameter("testbed.type", "accelerator")
            set_parameter("testbed.accelerator_model", available_resources.accelerator.model)
            set_parameter("testbed.accelerator_hwacc_type", available_resources.accelerator.hwacc_type)
            add_log_secret(available_resources.accelerator.id)
            set_parameter("testbed.accelerator_id", available_resources.accelerator.id)
            set_parameter("testbed.accelerator_cb_mode", available_resources.accelerator.cb_mode)
            set_parameter(
                "testbed.accelerator_pdsch_enc_nof_hwacc", available_resources.accelerator.pdsch_enc_nof_hwacc
            )
            set_parameter(
                "testbed.accelerator_pusch_dec_nof_hwacc", available_resources.accelerator.pusch_dec_nof_hwacc
            )
            set_parameter("testbed.accelerator_harq_context_size", available_resources.accelerator.harq_context_size)

        # ZMQ
        if available_resources.sdr is None and available_resources.ru is None:
            # In ZMQ, set sample rate and antennas to the max possible by the driver
            set_parameter("testbed.sample_rate", 122880000)
            set_parameter("ue.nof_antennas_dl", 4)
            set_parameter("ue.nof_antennas_ul", 4)
            set_parameter("gnb.nof_antennas_dl", 4)
            set_parameter("gnb.nof_antennas_ul", 4)

    ###########################
    # Folder and report logic #
    ###########################

    def get_current_report_folder(self) -> Path:
        """
        Get current Report folder. Create if not exists.
        """
        if self._current_report_folder is None:
            self._current_report_folder = self._base_folder.joinpath(now_timestamp_file())
            self._executor.mkdir(self._current_report_folder)
            logging.info("Starting a new log folder at %s", self._current_report_folder)
        return self._current_report_folder

    def get_filepath_in_report_folder(self, filename: str) -> str:
        """
        Create the file `filename` in the current report folder
        :param filename
        """
        return str(self.get_current_report_folder().joinpath(filename).resolve())

    def close_previous_report_folder(self):
        """
        End previous report folder. Next request to `get_filepath_in_report_folder`
        will create a new folder.
        """
        if self._current_report_folder is not None:
            self._executor.close_folder(self._current_report_folder)
        self._current_report_folder = None

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def _render(
        self,
        filename: str,
        templates: Dict[str, str],
        values: Dict,
        prefix: str = "",
        suffix: str = "",
    ) -> str:

        # Get conf file content
        file_content = ""
        for basename, content in templates.items():
            if not content and basename:
                # Get original template if not overwritten
                with template_path(basename, add_ext=True).open("r", encoding="utf-8") as tmp_file_descriptor:
                    content = tmp_file_descriptor.read()
            # Evaluate template
            file_content += (
                Template(content).render(
                    **values,
                    report_folder=str(self.get_current_report_folder().resolve()),
                    utc_timestamp=now_utc_timestamp(),
                )
                + os.linesep
            )
        # Remove multiple empty lines
        file_content = prefix + re.sub(r"\n\s*\n", "\n\n", file_content) + suffix

        # Write conf file content to file
        configuration_file_path = self.get_filepath_in_report_folder(filename)
        self._executor.write_file(configuration_file_path, file_content)
        return configuration_file_path

    ################
    # GRPC Service #
    ################

    def GetRetinaInfo(self, request: Empty, context: grpc.ServicerContext) -> RetinaInfo:
        self._install_runtime_dependencies()
        agent_version = version(retina.agent.__name__)
        sut_version = self._get_sut_version()

        logging.info("Retina Info: Agent %s - SUT %s", agent_version, sut_version)
        return RetinaInfo(
            agent_version=agent_version,
            sut_version=sut_version,
        )

    def _install_runtime_dependencies(self):
        if platform.system().lower() == "linux" and "ubuntu" in platform.version().lower():
            lib_folder = Path(tempfile.gettempdir()).joinpath(self.RUNTIME_LIBS_FOLDER)
            if lib_folder.exists():
                deb_path_array = tuple(lib_folder.glob("*.deb"))
                if deb_path_array:
                    logging.debug("Installing dependencies")
                    for line in self._executor.run_binary("apt", "update"):
                        logging.debug(line)
                    for deb_path in deb_path_array:
                        for line in self._executor.run_binary("apt", "install", "-y", deb_path):
                            logging.debug(line)

    @abstractmethod
    def _get_sut_version(self) -> str:
        pass

    def _parse_sut_version(self, text: Tuple[str], regex: str) -> str:
        for line in text:
            match = re.search(
                regex,
                line,
            )
            if match is not None:
                sut_version = match.group(1)
                break
        else:
            sut_version = "UNKNOWN"
        return str(sut_version)

    def SetParameter(self, request: Parameter, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            try:
                set_parameter(request.name, request.value, auto_convert=True)
            except KeyError as err:
                logging.warning(err)
        return Empty()

    def Stop(self, request: UInt32Value, context: Optional[grpc.ServicerContext]) -> StopResponse:
        self.close_previous_report_folder()
        self._last_artifact_id = None
        return StopResponse()

    def Shutdown(self, request: Empty, context: Optional[grpc.ServicerContext]) -> Empty:
        if self._shutdown_callback is not None:
            self._shutdown_callback()
        return Empty()

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        return Metrics()

    def GetArtifactsId(self, request: Empty, context: grpc.ServicerContext) -> StringValue:
        if self._last_artifact_id is None:
            for handler in logging.getLogger().handlers:
                handler.flush()
            self._last_artifact_id = calculate_folder_hash(self._base_folder)
        return StringValue(value=self._last_artifact_id)

    def DownloadArtifacts(self, request: Empty, context) -> Generator[BytesValue, None, None]:
        for chunk in archive_artifact_folder(self._base_folder):
            yield BytesValue(value=chunk)

    def _get_ping_binary(self, context: grpc.ServicerContext) -> Tuple[str, ...]:  # pylint: disable=unused-argument
        return ("ping",)

    def Ping(self, request: PingRequest, context: grpc.ServicerContext) -> PingResponse:
        cmd = [*self._get_ping_binary(context)]
        if request.count:
            cmd += [
                "-c",
                str(request.count),
            ]
        if request.interval:
            cmd += [
                "-i",
                str(request.interval),
            ]
        cmd += [request.address]

        logging.info("Ping executed: %s", " ".join(cmd))

        output = ""
        for line in self._executor.run_binary(*cmd, keeplinebreaks=False, timeout=None, raise_if_exit_code=False):
            logging.debug(line)
            output += line + os.linesep

        num_sent_re = re.search(self.PING_PACKET_SENT_REGEX, output)
        num_sent = int(num_sent_re.group(1)) if num_sent_re is not None else None

        num_received_re = re.search(self.PING_PACKAGE_RECEIVED_REGEX, output)
        num_received = int(num_received_re.group(1)) if num_received_re is not None else None

        rrt_re = re.search(self.PING_RTT_REGEX, output)
        return PingResponse(
            status=num_sent == num_received,
            sent=num_sent,
            received=num_received,
            min=float(rrt_re.group(1)) if rrt_re is not None else -1,
            avg=float(rrt_re.group(2)) if rrt_re is not None else -1,
            max=float(rrt_re.group(3)) if rrt_re is not None else -1,
            mdev=float(rrt_re.group(4)) if rrt_re is not None else -1,
        )


@contextmanager
def notify_grpc_exception(context: grpc.ServicerContext) -> Generator[None, None, None]:
    """
    Context manager that handles a GrpcException, logging it and aborting the rpc method
    """
    code = grpc.StatusCode.OK
    details: str = ""

    try:
        yield
    except Exception as exc_info:  # pylint: disable=broad-except
        code = {
            TimeoutError: grpc.StatusCode.DEADLINE_EXCEEDED,
            IndexError: grpc.StatusCode.OUT_OF_RANGE,
            KeyError: grpc.StatusCode.NOT_FOUND,
            TypeError: grpc.StatusCode.INVALID_ARGUMENT,
            ValueError: grpc.StatusCode.INVALID_ARGUMENT,
            AttributeError: grpc.StatusCode.INVALID_ARGUMENT,
            ChildProcessError: grpc.StatusCode.ABORTED,
        }.get(type(exc_info), grpc.StatusCode.UNKNOWN)

        # pretty print exception
        for trace in traceback.format_exception(None, value=exc_info, tb=exc_info.__traceback__):
            for line in trace.splitlines():
                logging.error(line)

        details = str(exc_info)

    if code is not grpc.StatusCode.OK:
        context.abort(
            code,
            details,
        )
