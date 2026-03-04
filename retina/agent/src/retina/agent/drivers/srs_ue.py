# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
SRS UE Agent
"""

import csv
import datetime
import ipaddress
import logging
from contextlib import suppress
from pathlib import Path
from threading import Thread
from time import sleep
from typing import Optional, Tuple

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import Metrics, StopResponse, UEDefinition
from retina.protocol.ue_pb2 import UEAttachedInfo, UEStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.ue import SubscriberWithStatus, UEDriver
from retina.agent.features.executor import LocalExecutor
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import template_defaults, testbed_defaults, ue_defaults
from retina.agent.tools.threading import join_thread, kill_thread
from retina.agent.tools.time import TimeoutHandler


class SrsUe(UEDriver, BaseDriverSutHandler):  # pylint: disable=too-many-instance-attributes
    """
    SRS UE Agent
    """

    SRS_BINARY_NAME: str = "srsue"
    SRS_STDOUT_NAME: str = "stdout"
    SRS_LOG_FILENAME: str = "ue.log"
    SRS_CONF_FILE_BASE_NAME: str = "srs_ue.conf"
    SRS_START_UP_TIMEOUT: int = 5
    SRS_STOP_TIMEOUT: int = 5
    SRS_WAIT_BEFORE_STOP: float = 3
    SRS_VERSION_REGEX: str = r"Version (\d+\.\d+(?:\.\d+)?)"
    SRS_UE_INFO_WAIT: float = 0.5

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._epc_mask: int
        self._subscriber_client: SubscriberWithStatus = SubscriberWithStatus("", 0)
        self._attach_thread = Thread(target=self._validate_attach)
        self._attach_info: Optional[UEAttachedInfo] = None
        self._ue_metric_src_file: str = ""
        self._ue_metric: Optional[Metrics] = None
        self._ue_metric_time_first: Optional[datetime.datetime] = None
        self._ue_metric_time_last: Optional[datetime.datetime] = None

    def _get_sut_version(self) -> str:
        output = tuple(
            self._executor.run_binary(
                self.SRS_BINARY_NAME,
                "-h",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        version: str = self._parse_sut_version(output, self.SRS_VERSION_REGEX)
        return version

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> UEDefinition:
        ue_definition: UEDefinition = super().GetDefinition(request, context)

        # Change the imsi by adding the internal subscriber_id
        # so each connection has a different subscriber
        ue_definition.subscriber.imsi = str(int(ue_definition.subscriber.imsi) + 1).zfill(
            len(ue_definition.subscriber.imsi)
        )

        # Add to the dictionary: peer - subscriber(+status)
        self._subscriber_client = SubscriberWithStatus(ue_definition.subscriber, 1)

        return ue_definition

    def Start(self, request: UEStartInfo, context: grpc.ServicerContext) -> Empty:
        self.Stop(UInt32Value(value=request.start_info.timeout), context)

        self._epc_mask = request.fivegc_definition.tun_mask

        config_file = self._render(
            filename=self.SRS_CONF_FILE_BASE_NAME,
            templates={self.SRS_CONF_FILE_BASE_NAME: template_defaults.main},
            values={
                **get_module_variables(testbed_defaults),
                **get_module_variables(ue_defaults),
                # Logging
                "log_filename": self.get_filepath_in_report_folder(self.SRS_LOG_FILENAME),
                "mac_filename": self.get_filepath_in_report_folder(ue_defaults.mac_filename),
                "mac_nr_filename": self.get_filepath_in_report_folder(ue_defaults.mac_nr_filename),
                "nas_filename": self.get_filepath_in_report_folder(ue_defaults.nas_filename),
                "metrics_filename": self.get_filepath_in_report_folder(ue_defaults.metrics_filename_csv),
                # RF driver
                "tx_port0": f"*:{testbed_defaults.port_array[0]}",
                "rx_port0": f"{request.du_definition[0].zmq_ip}:" f"{request.du_definition[0].zmq_port_array[0]}",
                "sdr_driver_args": f"type={testbed_defaults.model}," f"{testbed_defaults.args}",
                "tx_gain": testbed_defaults.tx_gain if ue_defaults.tx_gain < 0 else ue_defaults.tx_gain,
                "rx_gain": testbed_defaults.rx_gain if ue_defaults.rx_gain < 0 else ue_defaults.rx_gain,
                # Cell
                "band": ue_defaults.cells[0]["band"],
                "sample_rate": testbed_defaults.sample_rate if ue_defaults.sample_rate < 0 else ue_defaults.sample_rate,
                "net_mask": str(ipaddress.IPv4Network(f"0.0.0.0/{self._epc_mask}", strict=False).netmask),
                # UE List
                "subscriber": self._subscriber_client.subscriber,
            },
        )

        logfile = self.get_filepath_in_report_folder(self.SRS_STDOUT_NAME) + ".log"
        self._last_log_array = (
            logfile,
            self.get_filepath_in_report_folder(self.SRS_LOG_FILENAME),
        )

        # Launch
        self.start_sut(
            *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
            self.SRS_BINARY_NAME,
            config_file,
            *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
            logfile=self.get_filepath_in_report_folder(self.SRS_STDOUT_NAME + ".log"),
            dryrun=request.start_info.dryrun,
        )

        self._attach_info = None
        self._attach_thread = Thread(target=self._validate_attach, args=(context.peer(),))
        self._attach_thread.start()
        self._ue_metric = None
        self._ue_metric_time_first = None
        self._ue_metric_time_last = None
        self._ue_metric_src_file = self.get_filepath_in_report_folder(ue_defaults.metrics_filename_csv)

        subscriber_id = self._subscriber_client.subscriber_id
        self._subscriber_client.started = True
        logging.info("Power on user with id %s", subscriber_id)

        with suppress(BrokenPipeError, AttributeError):
            # Enter (stop previous command) + power_on + t
            self._process.stdin.write("\nt\n")
            self._process.stdin.flush()

        return Empty()

    def _validate_attach(self, _context_peer: str) -> None:
        subscriber_id = self._subscriber_client.subscriber_id
        result = self.read_from_log(
            (r"IP: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",),
            found_any=False,
            timeout=30,
        )

        # pylint: disable=unbalanced-tuple-unpacking
        _, ipv4 = result[0]

        logging.info("Attached user with id %s", subscriber_id)

        ue_id = 0
        rnti = 0
        pdn_id = ""
        ifname = ""
        ipv4_dns = ""
        ipv6 = ""
        ipv6_dns = ""
        ipv6_gateway = ""

        self._attach_info = UEAttachedInfo(
            ue_id=ue_id,
            pdn_id=pdn_id,
            interface=ifname,
            ipv4=ipv4,
            ipv4_dns=ipv4_dns,
            ipv4_gateway=str(ipaddress.ip_network(f"{ipv4}/{self._epc_mask}", False).network_address + 1),
            ipv6=ipv6,
            ipv6_dns=ipv6_dns,
            ipv6_gateway=ipv6_gateway,
            rnti=rnti,
        )

    # pylint: disable=inconsistent-return-statements
    def WaitUntilAttached(self, request: UInt32Value, context: grpc.ServicerContext) -> UEAttachedInfo:
        with notify_grpc_exception(context):
            timeout_handler = TimeoutHandler(request.value)
            while timeout_handler.not_reached():
                if self._attach_info is not None:
                    return self._attach_info
                sleep(self.SRS_UE_INFO_WAIT)

    def Stop(self, request: UInt32Value, context: Optional[grpc.ServicerContext]) -> StopResponse:
        # Kill attach thread if still alive and running
        if self._attach_thread.is_alive():
            kill_thread(self._attach_thread, TimeoutError())
            join_thread(self._attach_thread)
        response = super().Stop(request, context)
        self._parse_metrics()
        return response

    def _parse_metrics(self):
        if self._ue_metric_src_file and Path(self._ue_metric_src_file).exists() and self._ue_metric is None:
            self._ue_metric = Metrics()
            with open(self._ue_metric_src_file, "r", encoding="utf-8") as fd:
                reader = csv.DictReader(fd, delimiter=";")
                for ue_info in reader:
                    if ue_info["time"] == "#eof":
                        break
                    timestamp = datetime.datetime.fromtimestamp(int(ue_info["time"]) / 1000, tz=datetime.timezone.utc)
                    if self._ue_metric_time_first is None:
                        self._ue_metric = Metrics(
                            nof_ko_dl=int(float(ue_info["dl_bler"])),
                            dl_bitrate=float(ue_info["dl_brate"]),
                            nof_ko_ul=int(ue_info["ul_bler"]),
                            ul_bitrate=float(ue_info["ul_brate"]),
                        )
                        self._ue_metric_time_first = timestamp
                        self._ue_metric_time_last = timestamp
                    else:
                        self._ue_metric.nof_ko_dl += int(float(ue_info["dl_bler"]))
                        self._ue_metric.nof_ko_ul += int(float(ue_info["ul_bler"]))

                        if self._ue_metric_time_last is None:
                            self._ue_metric_time_last = self._ue_metric_time_first

                        t_old = (self._ue_metric_time_last - self._ue_metric_time_first).total_seconds()
                        t_new = (timestamp - self._ue_metric_time_last).total_seconds()
                        t_beginning = (timestamp - self._ue_metric_time_first).total_seconds()

                        self._ue_metric.dl_bitrate = (
                            (self._ue_metric.dl_bitrate * t_old) + (float(ue_info["dl_brate"]) * t_new)
                        ) / t_beginning
                        self._ue_metric.ul_bitrate = (
                            (self._ue_metric.ul_bitrate * t_old) + (float(ue_info["ul_brate"]) * t_new)
                        ) / t_beginning

                        self._ue_metric_time_last = timestamp

    @property
    def _expected_exit_code_array(self) -> Tuple[int, ...]:
        return (-9, -11)

    @property
    def _stop_count_regex(self) -> str:
        return r".*"

    @property
    def _warning_regex(self) -> str:
        return (
            self.SRS_WARNING_HEADER
            + r"(?!.*Option pdcch_cfg not present)"
            + r"(?!.*proc_time: detected long duration)"
            + self.SRS_WARNING_BODY
            + self.SRS_WERROR_FOOTER
        )

    @property
    def _error_regex(self) -> str:
        return (
            self.SRS_ERROR_HEADER
            + r"(?!.*Invalid config. Priority=1 already configured for lcg=0)"
            + r"(?!.*Couldn't register logical channel at BSR procedure.)"
            + self.SRS_WERROR_FOOTER
        )

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        metrics = super().GetMetrics(request, context)
        if self._ue_metric is not None:
            metrics.MergeFrom(self._ue_metric)
        return metrics

    SRS_WARNING_HEADER: str = r"^.*\[.*\[W\]"
    SRS_WARNING_BODY: str = (
        r"(?!.*Could not check scaling governor)"
        r"(?!.*Dropped GTP-U PDU, queue is full)"
        r"(?!.*uci slot.*not found)"
        r"(?!.*ACK Wait Timeout)"
        r"(?!.*build data PDU, tx_window is full)"
        r"(?!.*no metrics will be reported as no layer was enabled)"
        r"(?!.*Radio realtime event)"
        r"(?!.*Dropping SDU to avoid)"
        r"(?!.*Dropping UeContextReleaseCommand. UE does not exist)"
        r"(?!.*Real-time failure in RF: late)"
        r"(?!.*sysfs is not available.)"
        r"(?!.*RAPL MSR interface is not available.)"
    )
    SRS_ERROR_HEADER: str = r"^.*\[.*\[E\]"
    SRS_WERROR_FOOTER: str = r".*$"


class LocalSrsUe(SrsUe):
    """
    srsUE Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
