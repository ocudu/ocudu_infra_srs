# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
OCUDU DU Agent
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread
from time import sleep
from typing import Any, Dict, List, Optional, Tuple

import grpc
import websocket
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import (
    Metrics,
    NearRtRicDefinition,
    PLMN,
    StopResponse,
    UEDefinition,
)
from retina.protocol.gnb_pb2 import DUStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.gnb import DUDriver
from retina.agent.features.executor import LocalExecutor
from retina.agent.features.gnb_report import transform_metrics
from retina.agent.features.json_metrics.du_general import GeneralMetricsAnalyzer
from retina.agent.features.json_metrics.du_peak_average import PerUePeakAverageAnalyzer
from retina.agent.features.pcap.analyzer import run_analyzers
from retina.agent.features.pcap.rrc import (
    DrxLongCycleAnalyzer,
    HandoverAnalyzer,
    PagingAnalyzer,
    PrachConfigIndexAnalyzer,
    ReestablishmentAnalyzer,
    ResumeRequestAnalyzer,
    SibAnalyzer,
    SrsFreqDomainAnalyzer,
    SuspendConfigAnalyzer,
    T312Analyzer,
    TransformPrecoderAnalyzer,
)
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import gnb_defaults, template_defaults, testbed_defaults
from retina.agent.tools.threading import join_thread

_WS_ANALYZER_ARRAY = (GeneralMetricsAnalyzer, PerUePeakAverageAnalyzer)
_MAC_PCAP_ANALYZER_ARRAY = (
    ReestablishmentAnalyzer,
    PrachConfigIndexAnalyzer,
    SibAnalyzer,
    PagingAnalyzer,
    DrxLongCycleAnalyzer,
    T312Analyzer,
    SrsFreqDomainAnalyzer,
    ResumeRequestAnalyzer,
    SuspendConfigAnalyzer,
    TransformPrecoderAnalyzer,
)
_RLC_PCAP_ANALYZER_ARRAY = (
    ReestablishmentAnalyzer,
    HandoverAnalyzer,
    DrxLongCycleAnalyzer,
    T312Analyzer,
    SrsFreqDomainAnalyzer,
    TransformPrecoderAnalyzer,
)


@dataclass
class _CellInfo:
    pci: int
    sector_id: int
    cell_id: str
    prach_root_sequence_index: int
    neighbor_array: List = field(default_factory=list)


def get_cell_array(*, num_cells: int, cell_offset: int) -> Tuple[_CellInfo, ...]:
    """
    Return cell array information
    """
    cell_array = tuple(
        _CellInfo(
            pci=gnb_defaults.pci + i + cell_offset,
            sector_id=gnb_defaults.sector_id + i + cell_offset,
            cell_id=hex(gnb_defaults.gnb_id * 2 ** (36 - gnb_defaults.gnb_id_bit_length) + i + cell_offset),
            prach_root_sequence_index=gnb_defaults.prach_root_sequence_index + i + cell_offset,
        )
        for i in range(num_cells)
    )
    for i, cell_info in enumerate(cell_array):
        cell_info.neighbor_array = [*cell_array[0:i], *cell_array[i + 1 : len(cell_array) + 1]]
    return cell_array


# pylint: disable=too-many-instance-attributes
class OcuduDu(DUDriver, BaseDriverSutHandler):
    """
    OCUDU DU Agent
    """

    DU_BINARY_NAME: str = "odu"
    DU_STDOUT_NAME: str = "stdout_du"
    DU_LOG_FILENAME: str = "du.log"
    DU_TRACING_FILENAME: str = "tracing.json"
    DU_VERSION_REGEX: str = r"(\d+\.\d+(?:\.\d+)? \(\w+\))"
    DU_CONF_FINAL_NAME: str = "ocudu_du.yml"
    DU_CONF_MAIN_NAME: str = "ocudu_gnb_base.yml"
    DU_CONF_DU_NAME: str = "ocudu_gnb_du.yml"
    DU_CONF_RU_NAME: str = "ocudu_gnb_ru.yml"
    DU_QOS_NAME: str = "ocudu_gnb_qos.yml"
    DU_CONF_METRICS_NAME: str = "ocudu_gnb_metrics.yml"
    DU_START_UP_TIMEOUT: int = 5
    _METRICS_ENCODING: str = "utf-8"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        logging.getLogger("websocket").setLevel(logging.CRITICAL)
        self._ws_app = websocket.WebSocketApp(
            "ws://127.0.0.1:8001",
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_close=self._on_ws_close,
            on_error=self._on_ws_error,
        )
        self._metrics = Metrics()
        self._ws_analyzers = tuple(analyzer_cls() for analyzer_cls in _WS_ANALYZER_ARRAY)
        self._metrics_thread = Thread(target=self._metrics_listener)
        self._metrics_thread_stopper = Event()
        self._metrics_parsing_done = True

    def _get_sut_version(self) -> str:
        output = tuple(
            self._executor.run_binary(
                self.DU_BINARY_NAME,
                "-v",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        version: str = self._parse_sut_version(output, self.DU_VERSION_REGEX)
        return version

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def get_parameters(
        self,
        *,
        ue_definition: UEDefinition,
        gnb_du_id: int,
        plmn: PLMN,
        num_cells: int = 1,
        cell_offset: int = 0,
        ric_definition: Optional[NearRtRicDefinition] = None,
    ) -> Dict[str, Any]:
        """
        Return parameters for config templates
        """
        return {
            "gnb_du_id": gnb_du_id,
            "mac_filename": self.get_filepath_in_report_folder(gnb_defaults.mac_filename),
            "rlc_filename": self.get_filepath_in_report_folder(gnb_defaults.rlc_filename),
            "tracing_filename": self.get_filepath_in_report_folder(self.DU_TRACING_FILENAME),
            "zmq_def": (
                ",".join(
                    f"tx_port{i}=tcp://*:{testbed_defaults.port_array[i + cell_offset]},"
                    f"rx_port{i}=tcp://{ue_definition.zmq_ip}:" + str(ue_definition.zmq_port_array[i + cell_offset])
                    for i in range(num_cells * max(gnb_defaults.nof_antennas_dl, gnb_defaults.nof_antennas_ul))
                )
                if testbed_defaults.type == "zmq"
                else ""
            ),
            "sdr_driver_args": f"type={testbed_defaults.model}," f"{testbed_defaults.args}",
            "sync": testbed_defaults.sync if testbed_defaults.sync != "none" else "default",
            "sample_rate": (testbed_defaults.sample_rate if gnb_defaults.sample_rate < 0 else gnb_defaults.sample_rate),
            "tx_gain": testbed_defaults.tx_gain if gnb_defaults.tx_gain < 0 else gnb_defaults.tx_gain,
            "rx_gain": testbed_defaults.rx_gain if gnb_defaults.rx_gain < 0 else gnb_defaults.rx_gain,
            "mcc": plmn.mcc,
            "mnc": plmn.mnc,
            "cell_array": get_cell_array(
                num_cells=num_cells,
                cell_offset=cell_offset if cell_offset is not None else 0,
            ),
            "e2_du_enable": (ric_definition.enabled if ric_definition else False),
            "e2ap_du_filename": (
                self.get_filepath_in_report_folder(gnb_defaults.e2ap_du_filename) if ric_definition else ""
            ),
            "ric_ip": (ric_definition.ric_ip if ric_definition else ""),
            "ric_port": (ric_definition.ric_port if ric_definition else ""),
        }

    def Start(self, request: DUStartInfo, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            self.Stop(UInt32Value(value=request.start_info.timeout), context)

            du_conf_file = self._render(
                filename=self.DU_CONF_FINAL_NAME,
                templates={
                    self.DU_CONF_METRICS_NAME: "",
                    self.DU_CONF_MAIN_NAME: template_defaults.main,
                    self.DU_CONF_DU_NAME: template_defaults.du,
                    self.DU_CONF_RU_NAME: template_defaults.ru,
                    self.DU_QOS_NAME: template_defaults.qos,
                },
                values={
                    **get_module_variables(testbed_defaults),
                    **get_module_variables(gnb_defaults),
                    **self.get_parameters(
                        ue_definition=request.ue_definition,
                        gnb_du_id=request.gnb_du_id,
                        plmn=request.plmn,
                        num_cells=request.num_cells,
                        cell_offset=request.cell_offset,
                        ric_definition=request.ric_definition,
                    ),
                    "log_filename": self.get_filepath_in_report_folder(self.DU_LOG_FILENAME),
                    "cu_ip": request.cu_definition.cu_ip,
                    "du_ip": testbed_defaults.ip,
                },
            )

            du_logfile = self.get_filepath_in_report_folder(self.DU_STDOUT_NAME) + ".log"
            self._last_log_array = (
                du_logfile,
                self.get_filepath_in_report_folder(self.DU_LOG_FILENAME),
            )

            # Start DU binary
            self.start_sut(
                *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
                self.DU_BINARY_NAME,
                "-c",
                du_conf_file,
                *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
                logfile=du_logfile,
                dryrun=request.start_info.dryrun,
            )

            # Wait for DU to start
            if not request.start_info.dryrun:
                try:
                    self.read_from_log(
                        (r"==== DU started ===",),
                        True,
                        timeout=request.start_info.timeout if request.start_info.timeout else self.DU_START_UP_TIMEOUT,
                    )
                except TimeoutError as err:
                    logging.warning("Timeout reached while looking for DU starting reference.")
                    if not self._is_alive:
                        with notify_grpc_exception(context):
                            raise err from None

                self.start_listening_metrics()

        return Empty()

    def start_listening_metrics(self):
        """
        Start listening metrics
        """
        self._metrics = Metrics()
        self._metrics_parsing_done = False
        self._ws_analyzers = tuple(analyzer_cls() for analyzer_cls in _WS_ANALYZER_ARRAY)
        self._metrics_thread = Thread(target=self._metrics_listener)
        self._metrics_thread_stopper = Event()
        self._metrics_thread.start()

    def _metrics_listener(self):
        # Keep it running until the stopper is set (or the WebSocket connection is closed)
        while not self._metrics_thread_stopper.is_set() and self._ws_app.run_forever():
            sleep(1)
        # Close brackets in the metrics file
        with open(
            self.get_filepath_in_report_folder(gnb_defaults.metrics_filename_json),
            "a",
            encoding=self._METRICS_ENCODING,
        ) as fd:
            fd.write("]")

    def _on_ws_open(self, ws: websocket.WebSocketApp):
        logging.info("WebSocket connection opened")
        # Create metrics file and write the opening bracket
        with open(
            self.get_filepath_in_report_folder(gnb_defaults.metrics_filename_json),
            "w+",
            encoding=self._METRICS_ENCODING,
        ) as fd:
            fd.write("[")
        # Subscribe to metrics
        ws.send(json.dumps({"cmd": "metrics_subscribe"}))

    def _on_ws_message(self, _ws: websocket.WebSocketApp, message: str):
        try:
            metric_info = json.loads(message)
            if "cmd" not in metric_info:
                for analyzer in self._ws_analyzers:
                    try:
                        analyzer.process(metric_info)
                    except Exception:  # pylint: disable=broad-except
                        logging.exception("Error in %s while processing metric", type(analyzer).__name__)
                with open(
                    self.get_filepath_in_report_folder(gnb_defaults.metrics_filename_json),
                    "a",
                    encoding=self._METRICS_ENCODING,
                ) as fd:
                    if fd.tell() > 1:  # If not the first line, add a comma
                        fd.write("," + os.linesep)
                    fd.write(json.dumps(metric_info))
        except json.JSONDecodeError:
            logging.error("Error decoding json - Ignoring this message: %s", message)

    def _on_ws_close(self, _ws: websocket.WebSocketApp, status_code: int, msg: str):
        logging.info("WebSocket connection closed. code: %s, msg: %s.", status_code, msg)

    def _on_ws_error(self, _ws: websocket.WebSocketApp, error: Exception):
        if not isinstance(error, (websocket.WebSocketConnectionClosedException, ConnectionRefusedError)):
            logging.exception(error)

    def stop_listening_metrics(self) -> str:
        """
        Stop listening to metrics
        """
        metrics_json_path = ""
        if self._metrics_thread.is_alive():
            self._metrics_thread_stopper.set()
            self._ws_app.close()
            join_thread(self._metrics_thread)
            metrics_json_path = self.get_filepath_in_report_folder(gnb_defaults.metrics_filename_json)
        return metrics_json_path

    def get_metrics_parsing_arguments(self) -> Tuple[str, ...]:
        """
        Get Arguments for metrics parsing. Needs to be called before stop
        """
        if self._metrics_parsing_done:
            return tuple()
        return (
            self.get_filepath_in_report_folder(gnb_defaults.rlc_filename),
            self.get_filepath_in_report_folder(gnb_defaults.mac_filename),
        )

    def extract_metrics(self, *args):
        """
        Extract Metrics
        """
        if not self._metrics_parsing_done:
            rlc_pcap_filename, mac_pcap_filename = args
            for ws_analyzer in self._ws_analyzers:
                self._metrics.MergeFrom(ws_analyzer.report())
            if Path(mac_pcap_filename).exists():
                self._metrics.MergeFrom(
                    run_analyzers(
                        mac_pcap_filename,
                        tuple(analyzer_cls() for analyzer_cls in _MAC_PCAP_ANALYZER_ARRAY),
                        "--enable-heuristic mac_nr_udp",
                    )
                )
                self._metrics_parsing_done = True
            if Path(rlc_pcap_filename).exists():
                self._metrics.MergeFrom(
                    run_analyzers(
                        rlc_pcap_filename,
                        tuple(analyzer_cls() for analyzer_cls in _RLC_PCAP_ANALYZER_ARRAY),
                        "--enable-heuristic rlc_nr_udp",
                    )
                )
                self._metrics_parsing_done = True

    def Stop(self, request: UInt32Value, context: grpc.ServicerContext) -> StopResponse:
        metrics_json_path = self.stop_listening_metrics()
        pcap_args = self.get_metrics_parsing_arguments()
        response = super().Stop(request, context)
        self.extract_metrics(*pcap_args)
        transform_metrics(metrics_json_path)
        return response

    @property
    def _warning_regex(self) -> str:
        return OCUDU_WARNING_HEADER + OCUDU_DU_WARNING_BODY + gnb_defaults.warning_extra_regex + OCUDU_WERROR_FOOTER

    @property
    def _error_regex(self) -> str:
        return r"(?:" + RTSAN_ERROR + ")|(?:" + OCUDU_ERROR_HEADER + OCUDU_WERROR_FOOTER + r")"

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        metrics = super().GetMetrics(request, context)
        metrics.MergeFrom(self._metrics)
        return metrics


RTSAN_ERROR = r".*==ERROR.*$"
OCUDU_ERROR_HEADER: str = r"^.*\[.*\[E\]"
OCUDU_WARNING_HEADER: str = r"^.*\[.*\[W\]"
OCUDU_DU_WARNING_BODY: str = (
    r"(?!.*Could not check scaling governor)"
    r"(?!.*uci slot.*not found)"
    r"(?!.*ACK Wait Timeout)"
    r"(?!.*build data PDU, tx_window is full)"
    r"(?!.*Radio realtime event)"
    r"(?!.*Dropping SDU to avoid)"
    r"(?!.*Real-time failure in RF: late)"
    r"(?!.*sysfs is not available.)"
    r"(?!.*RAPL MSR interface is not available.)"
)
OCUDU_WERROR_FOOTER: str = r".*$"


class LocalOcuduDu(OcuduDu):
    """
    OCUDU DU Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
