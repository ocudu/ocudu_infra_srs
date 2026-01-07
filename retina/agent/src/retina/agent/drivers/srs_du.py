#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
SrsDu Agent
"""

import datetime
import json
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from threading import Event, Thread
from time import sleep
from typing import Any, Deque, Dict, List, Optional, Tuple

import grpc
import websocket
from google.protobuf.empty_pb2 import Empty
from google.protobuf.text_format import MessageToString
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import (
    CellMetrics,
    Metrics,
    NearRtRicDefinition,
    PLMN,
    StopResponse,
    UEDefinition,
    UeMetrics,
)
from retina.protocol.gnb_pb2 import DUStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.gnb import DUDriver
from retina.agent.features.executor import LocalExecutor
from retina.agent.features.gnb_report import transform_metrics
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import gnb_defaults, template_defaults, testbed_defaults
from retina.agent.tools.threading import join_thread


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


class MovingAverage:
    """
    Implement a Moving Average Queue for N samples
    """

    def __init__(self, max_queue_length):
        self.queue: Deque[int] = deque(maxlen=max_queue_length)

    def get_average(self, nof_average_samples=None) -> float:
        """
        Return the average of the last K elements in the queue
        """
        if nof_average_samples is None:
            nof_average_samples = self.queue.maxlen
        elif nof_average_samples > self.queue.maxlen or nof_average_samples < 0:
            raise ValueError("nof_average_samples is greater than the maximum length of the queue")
        if len(self.queue) == 0:
            return 0
        last_k_values = list(self.queue)[-nof_average_samples:]
        return sum(last_k_values) / len(last_k_values)

    def add(self, *, value, nof_average_samples=None) -> float:
        """
        Add a new element to the queue
        """
        self.queue.append(value)
        return self.get_average(nof_average_samples)

    # pylint: disable=missing-function-docstring
    def get_all(self) -> list[float]:
        return list(self.queue)


# pylint: disable=too-many-instance-attributes
class SrsDu(DUDriver, BaseDriverSutHandler):
    """
    SrsDu Agent
    """

    DU_BINARY_NAME: str = "srsdu"
    DU_STDOUT_NAME: str = "stdout_du"
    DU_LOG_FILENAME: str = "du.log"
    DU_TRACING_FILENAME: str = "tracing.json"
    DU_VERSION_REGEX: str = r"(\d+\.\d+(?:\.\d+)? \(\w+\))"
    DU_CONF_FINAL_NAME: str = "srs_du.yml"
    DU_CONF_MAIN_NAME: str = "srs_gnb_base.yml"
    DU_CONF_DU_NAME: str = "srs_gnb_du.yml"
    DU_CONF_RU_NAME: str = "srs_gnb_ru.yml"
    DU_QOS_NAME: str = "srs_gnb_qos.yml"
    DU_CONF_METRICS_NAME: str = "srs_gnb_metrics.yml"
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
        self._aggregate_metrics = UeMetrics()
        self._cell_agg_metrics = CellMetrics()
        self._metrics_thread = Thread(target=self._metrics_listener)
        self._metrics_thread_stopper = Event()
        self._metrics_dict: Dict[int, Dict[int, UeMetrics]] = {}
        self._reports_since_last_ue_event: Dict[int, int] = {}
        self._prev_ue_list: List = []
        # Moving average for DL/UL bitrate, max 50 samples, for the aggregate nd UE metrics, respectively
        self._dl_brate_mov_av = MovingAverage(50)
        self._ul_brate_mov_av = MovingAverage(50)
        self._ues_dl_brate_mov_av: Dict[int, Dict[int, MovingAverage]] = {}
        self._ues_ul_brate_mov_av: Dict[int, Dict[int, MovingAverage]] = {}

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
        self._metrics_dict.clear()
        self._aggregate_metrics = UeMetrics()
        self._cell_agg_metrics = CellMetrics()
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
            if "cmd" not in metric_info and self._parse_metrics(metric_info):
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

    # pylint: disable=too-many-branches
    def _parse_metrics(self, metric_info: Dict) -> bool:

        parsed = False

        timestamp = Timestamp()
        timestamp.FromDatetime(datetime.datetime.fromisoformat(metric_info["timestamp"].strip()))

        for cell_info in metric_info.get("cells", []):

            if "cell_metrics" in cell_info and cell_info["cell_metrics"]:
                # Total metrics: Initialize time in metric the first time
                parsed = True

                if self._cell_agg_metrics.time_first.seconds == 0:
                    self._cell_agg_metrics.time_first.CopyFrom(timestamp)
                else:
                    # Filtering out first value
                    self._cell_agg_metrics.error_indication_cnt += cell_info["cell_metrics"]["error_indication_count"]

                self._cell_agg_metrics.av_latency += cell_info["cell_metrics"]["average_latency"]
                self._cell_agg_metrics.max_latency = max(
                    self._cell_agg_metrics.max_latency, cell_info["cell_metrics"]["max_latency"]
                )
                self._cell_agg_metrics.max_late_dl_harqs = max(
                    self._cell_agg_metrics.max_late_dl_harqs, cell_info["cell_metrics"]["late_dl_harqs"]
                )
                self._cell_agg_metrics.max_late_ul_harqs = max(
                    self._cell_agg_metrics.max_late_ul_harqs, cell_info["cell_metrics"]["late_ul_harqs"]
                )

                self._cell_agg_metrics.time_last.CopyFrom(timestamp)

            # Ignore other metrics
            if "ue_list" in cell_info:
                # Total metrics: Initialize time in metric the first time
                parsed = True

                if self._aggregate_metrics.time_first.seconds == 0:
                    if not cell_info["ue_list"]:
                        return parsed
                    self._aggregate_metrics.time_first.CopyFrom(timestamp)
                    self._aggregate_metrics.time_last.CopyFrom(timestamp)

                # Create dicts for the aggregate info of all UEs
                total_info = {
                    "dl_nof_ok": 0,
                    "dl_nof_nok": 0,
                    "ul_nof_ok": 0,
                    "ul_nof_nok": 0,
                    "dl_brate": 0,
                    "ul_brate": 0,
                }
                prev_total_info = {
                    "nof_pucch_f0f1_invalid_harqs": 0,
                    "nof_pucch_f2f3f4_invalid_harqs": 0,
                    "nof_pucch_f2f3f4_invalid_csis": 0,
                }

                self._handle_metric_events(cell_info)

                for ue_info in cell_info["ue_list"]:
                    pci, rnti = ue_info["pci"], ue_info["rnti"]

                    # Initialize UE metric the first time
                    if pci not in self._metrics_dict:
                        self._metrics_dict[pci] = {}
                        self._ues_dl_brate_mov_av[pci] = {}
                        self._ues_ul_brate_mov_av[pci] = {}
                    if rnti not in self._metrics_dict[pci]:
                        self._metrics_dict[pci][rnti] = UeMetrics(
                            pci=pci,
                            rnti=rnti,
                            time_first=Timestamp(seconds=timestamp.seconds, nanos=timestamp.nanos),
                            time_last=Timestamp(seconds=timestamp.seconds, nanos=timestamp.nanos),
                        )
                        self._ues_dl_brate_mov_av[pci][rnti] = MovingAverage(50)
                        self._ues_ul_brate_mov_av[pci][rnti] = MovingAverage(50)

                    # Populate the metric
                    self._populate_metric(timestamp, self._metrics_dict[pci][rnti], ue_info)
                    self._populate_moving_av_metrics(self._metrics_dict[pci][rnti], ue_info, (pci, rnti))

                    # Aggregate values
                    for key in total_info:
                        total_info[key] += ue_info[key]

                # Update the metrics that are only counted if no recent UE events have been registered
                # By recent we mean either in this report, the previous or the next one
                for ue_info in self._prev_ue_list:
                    pci, rnti = ue_info["pci"], ue_info["rnti"]

                    if (
                        rnti not in self._reports_since_last_ue_event
                        and pci in self._metrics_dict
                        and rnti in self._metrics_dict[pci]
                    ):
                        # Populate the metric
                        self._populate_metric_prev(self._metrics_dict[pci][rnti], ue_info)

                        # Aggregate values
                        for key in prev_total_info:
                            prev_total_info[key] += ue_info[key]

                # Total metrics
                self._populate_metric(timestamp, self._aggregate_metrics, total_info)
                self._populate_moving_av_metrics(self._aggregate_metrics, total_info, None)
                self._populate_metric_prev(self._aggregate_metrics, prev_total_info)
                # Keep the list of UEs for the next iteration
                self._prev_ue_list = cell_info["ue_list"]

        return parsed

    def _handle_metric_events(self, metric_info: Dict):
        # Update the recent events dict
        for rnti in list(self._reports_since_last_ue_event.keys()):
            self._reports_since_last_ue_event[rnti] += 1
            # No need to keep updating, just delete the entry
            if self._reports_since_last_ue_event[rnti] > 1:
                del self._reports_since_last_ue_event[rnti]

        # Check for UE events
        for event in metric_info.get("event_list", []):
            if event["event_type"] in ("ue_create", "ue_reconf", "ue_rem"):
                rnti = event["rnti"]
                self._reports_since_last_ue_event[rnti] = 0

    def _populate_metric(
        self,
        timestamp: Timestamp,
        metric: UeMetrics,
        info: Dict,
    ):
        metric.dl_nof_ok += info["dl_nof_ok"]
        metric.dl_nof_ko += info["dl_nof_nok"]
        metric.ul_nof_ok += info["ul_nof_ok"]
        metric.ul_nof_ko += info["ul_nof_nok"]

        metric.dl_bitrate_min = min(metric.dl_bitrate_min, info["dl_brate"])
        metric.dl_bitrate_max = max(metric.dl_bitrate_max, info["dl_brate"])

        metric.ul_bitrate_min = min(metric.ul_bitrate_min, info["ul_brate"])
        metric.ul_bitrate_max = max(metric.ul_bitrate_max, info["ul_brate"])

        t_old = (metric.time_last.ToDatetime() - metric.time_first.ToDatetime()).total_seconds()
        t_new = (timestamp.ToDatetime() - metric.time_last.ToDatetime()).total_seconds()
        t_beginning = (timestamp.ToDatetime() - metric.time_first.ToDatetime()).total_seconds()

        if t_beginning == 0:
            metric.dl_bitrate = info["dl_brate"]
            metric.ul_bitrate = info["ul_brate"]
        else:
            metric.dl_bitrate = ((metric.dl_bitrate * t_old) + (info["dl_brate"] * t_new)) / t_beginning
            metric.ul_bitrate = ((metric.ul_bitrate * t_old) + (info["ul_brate"] * t_new)) / t_beginning

        metric.time_last.CopyFrom(timestamp)

    def _populate_metric_prev(self, metric: UeMetrics, prev_info: Dict):
        metric.nof_pucch_f0f1_invalid_harqs += prev_info["nof_pucch_f0f1_invalid_harqs"]
        metric.nof_pucch_f2f3f4_invalid_harqs += prev_info["nof_pucch_f2f3f4_invalid_harqs"]
        metric.nof_pucch_f2f3f4_invalid_csis += prev_info["nof_pucch_f2f3f4_invalid_csis"]

    def _populate_moving_av_metrics(self, metric: UeMetrics, info: Dict, ue_pci_rnti: Optional[Tuple[int, int]]):
        # Populates the moving average bitrates.

        # Saves the peak (computed as max) average bitrates over N samples.
        if ue_pci_rnti is None:
            dl_brate_mov_av_5 = self._dl_brate_mov_av.add(value=info["dl_brate"], nof_average_samples=5)
            dl_brate_mov_av_15 = self._dl_brate_mov_av.get_average(15)
            dl_brate_mov_av_30 = self._dl_brate_mov_av.get_average(30)
            ul_brate_mov_av_5 = self._ul_brate_mov_av.add(value=info["ul_brate"], nof_average_samples=5)
            ul_brate_mov_av_15 = self._ul_brate_mov_av.get_average(15)
            ul_brate_mov_av_30 = self._ul_brate_mov_av.get_average(30)
        else:
            pci, rnti = ue_pci_rnti
            dl_brate_mov_av_5 = self._ues_dl_brate_mov_av[pci][rnti].add(value=info["dl_brate"], nof_average_samples=5)
            dl_brate_mov_av_15 = self._ues_dl_brate_mov_av[pci][rnti].get_average(15)
            dl_brate_mov_av_30 = self._ues_dl_brate_mov_av[pci][rnti].get_average(30)
            ul_brate_mov_av_5 = self._ues_ul_brate_mov_av[pci][rnti].add(value=info["ul_brate"], nof_average_samples=5)
            ul_brate_mov_av_15 = self._ues_ul_brate_mov_av[pci][rnti].get_average(15)
            ul_brate_mov_av_30 = self._ues_ul_brate_mov_av[pci][rnti].get_average(30)

        metric.dl_bitrate_peak_av.av_5_samples = max(metric.dl_bitrate_peak_av.av_5_samples, dl_brate_mov_av_5)
        metric.dl_bitrate_peak_av.av_15_samples = max(metric.dl_bitrate_peak_av.av_15_samples, dl_brate_mov_av_15)
        metric.dl_bitrate_peak_av.av_30_samples = max(metric.dl_bitrate_peak_av.av_30_samples, dl_brate_mov_av_30)
        metric.ul_bitrate_peak_av.av_5_samples = max(metric.ul_bitrate_peak_av.av_5_samples, ul_brate_mov_av_5)
        metric.ul_bitrate_peak_av.av_15_samples = max(metric.ul_bitrate_peak_av.av_15_samples, ul_brate_mov_av_15)
        metric.ul_bitrate_peak_av.av_30_samples = max(metric.ul_bitrate_peak_av.av_30_samples, ul_brate_mov_av_30)

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

    def Stop(self, request: UInt32Value, context: grpc.ServicerContext) -> StopResponse:
        metrics_json_path = self.stop_listening_metrics()
        response = super().Stop(request, context)
        transform_metrics(metrics_json_path)
        return response

    @property
    def _warning_regex(self) -> str:
        return SRS_WARNING_HEADER + DU_WARNING_BODY + gnb_defaults.warning_extra_regex + SRS_WERROR_FOOTER

    @property
    def _error_regex(self) -> str:
        return r"(?:" + RTSAN_ERROR + ")|(?:" + SRS_ERROR_HEADER + SRS_WERROR_FOOTER + r")"

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        metrics = super().GetMetrics(request, context)
        metrics.ue_array.extend(
            [ue_metric for ue_dict in self._metrics_dict.values() for ue_metric in ue_dict.values()]
        )
        metrics.total.CopyFrom(self._aggregate_metrics)
        metrics.cell.CopyFrom(self._cell_agg_metrics)
        logging.info("Metrics: %s", MessageToString(metrics, as_one_line=True))
        return metrics


RTSAN_ERROR = r".*==ERROR.*$"
SRS_ERROR_HEADER: str = r"^.*\[.*\[E\]"
SRS_WARNING_HEADER: str = r"^.*\[.*\[W\]"
DU_WARNING_BODY: str = (
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
SRS_WERROR_FOOTER: str = r".*$"


class LocalSrsDu(SrsDu):
    """
    SrsDu Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
