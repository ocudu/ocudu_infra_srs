#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Flexric RIC Agent
"""

import logging
import os
import re
from typing import Dict, Tuple

import grpc
import psutil
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.ric_pb2 import KpmMonXappRequest, NearRtRicStartInfo, NearRtRicSummary, RcXappRequest

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.ric import NearRtRicDriver
from retina.agent.features.executor import LocalExecutor
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import template_defaults, testbed_defaults
from retina.agent.tools.time import now_timestamp_file


class FlexricRic(NearRtRicDriver, BaseDriverSutHandler):
    """
    Flexric RIC Agent
    """

    FLEXRIC_BINARY_NAME: str = "/flexric/build/examples/ric/nearRT-RIC"
    FLEXRIC_STDOUT_NAME: str = "ric_stdout"
    FLEXRIC_CONF_FILE_BASE_NAME: str = "flexric.conf"
    FLEXRIC_START_UP_TIMEOUT: int = 3

    def __init__(self, *args, **kwargs) -> None:
        self._xapp_process_dict: Dict[str, psutil.Process] = {}
        self._xapp_log_dict: Dict[str, str] = {}
        self.ric_logfile = None
        self.ric_summary_report = NearRtRicSummary()
        super().__init__(*args, **kwargs)

    def _get_sut_version(self) -> str:
        return ""

    def Start(self, request: NearRtRicStartInfo, context: grpc.ServicerContext) -> Empty:
        self.Stop(UInt32Value(value=request.start_info.timeout), context)

        # reset RIC stats
        self.ric_summary_report = NearRtRicSummary()

        config_file = self._render(
            filename=self.FLEXRIC_CONF_FILE_BASE_NAME,
            templates={self.FLEXRIC_CONF_FILE_BASE_NAME: template_defaults.main},
            values={**get_module_variables(testbed_defaults)},
        )

        # Launch
        self.ric_logfile = self.get_filepath_in_report_folder(self.FLEXRIC_STDOUT_NAME) + ".log"
        self._last_log_array = (self.ric_logfile,)

        self.start_sut(
            *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
            "stdbuf",
            "-oL",
            "-eL",  # needed to flush std to file
            self.FLEXRIC_BINARY_NAME,
            "-c",
            config_file,
            *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
            dryrun=request.start_info.dryrun,
            logfile=self.ric_logfile,
        )

        # Wait until RIC is up and running
        if not request.start_info.dryrun:
            try:
                self.read_from_log(
                    (r"Initializing Task Manager",),
                    True,
                    timeout=request.start_info.timeout if request.start_info.timeout else self.FLEXRIC_START_UP_TIMEOUT,
                )
            except TimeoutError as err:
                logging.warning("Timeout reached while looking for RIC starting reference.")
                if not self._is_alive:
                    with notify_grpc_exception(context):
                        raise err from None

        logging.info("RIC started")
        return Empty()

    def StartKpmMonXapp(self, request: KpmMonXappRequest, context: grpc.ServicerContext) -> Empty:
        logging.info(
            "Flexric StartKpmMonXapp: Report Style: %i, Metrics: %s", request.report_service_style, request.metrics
        )

        if "kpm_mon_xapp" in self._xapp_process_dict:
            self.StopKpmMonXapp(Empty(), context)

        # generate config from template
        metrics_array = request.metrics.split(",")
        kpm_mon_xapp_conf_file_base_name: str = "flexric_kpm_mon_xapp.conf"
        config_file = self._render(
            filename=kpm_mon_xapp_conf_file_base_name,
            templates={kpm_mon_xapp_conf_file_base_name: template_defaults.main},
            values={
                "ric_ip": testbed_defaults.ip,
                "ran_type": "ngran_gNB_DU",
                "report_service_style": request.report_service_style,
                "metrics": metrics_array,
            },
        )
        # create logfile
        logfile = self.get_filepath_in_report_folder(f"kpm_mon_xapp_{now_timestamp_file()}.log")
        logfile_descriptor = open(logfile, "w", encoding="utf-8")  # pylint: disable=consider-using-with

        cmd = (
            "stdbuf",
            "-oL",
            "-eL",  # needed to flush std to file
            "/flexric/build/examples/xApp/c/monitor/xapp_oran_moni",
            "-c",
            config_file,
        )

        self._xapp_process_dict["kpm_mon_xapp"] = self._executor.create_process(*cmd, logfile=logfile_descriptor)
        self._xapp_log_dict["kpm_mon_xapp"] = logfile
        logging.info("KPM Monitor xApp executed: %s, Logfile: %s", " ".join(cmd), logfile)
        return Empty()

    def StopKpmMonXapp(self, request: Empty, context: grpc.ServicerContext) -> Empty:
        process = self._xapp_process_dict.pop("kpm_mon_xapp", None)
        if process is not None and self._executor.is_process_alive(process):
            self._executor.exit_process(process)

        logfile = self._xapp_log_dict.pop("kpm_mon_xapp", "")
        if logfile:
            text = ""
            with open(logfile, "r", encoding="UTF-8") as file:
                for line in file.readlines():
                    text += line.rstrip() + os.linesep

                nof_indications = len(re.findall(r"ind_msg.*from E2-node", text, flags=re.MULTILINE))
                nof_sub_reqs = len(re.findall(r"SUBSCRIPTION REQUEST tx", text, flags=re.MULTILINE))
                nof_sub_reps = len(re.findall(r"SUBSCRIPTION RESPONSE rx", text, flags=re.MULTILINE))

                logging.info("KPM Monitor xApp received: %i indication msgs", int(nof_indications))
                # collect stats for the final report
                self.ric_summary_report.nof_ric_indication += int(nof_indications)
                self.ric_summary_report.nof_subscription_reqs += int(nof_sub_reqs)
                self.ric_summary_report.nof_subscription_reps += int(nof_sub_reps)

        return Empty()

    def StartRcXapp(self, request: RcXappRequest, context: grpc.ServicerContext) -> Empty:
        logging.info(
            "Flexric StartRcXapp: Control Style: %i, Action Id: %s", request.control_service_style, request.action_id
        )

        if "rc_slice_xapp" in self._xapp_process_dict:
            self.StopRcXapp(Empty(), context)

        # generate config from template
        rc_slice_xapp_conf_file_base_name: str = "flexric_rc_slice_xapp.conf"
        config_file = self._render(
            filename=rc_slice_xapp_conf_file_base_name,
            templates={rc_slice_xapp_conf_file_base_name: template_defaults.main},
            values={"ric_ip": testbed_defaults.ip, "ran_type": "ngran_gNB_DU"},
        )
        # create logfile
        logfile = self.get_filepath_in_report_folder(f"rc_slice_xapp_{now_timestamp_file()}.log")
        logfile_descriptor = open(logfile, "w", encoding="utf-8")  # pylint: disable=consider-using-with

        cmd = (
            "stdbuf",
            "-oL",
            "-eL",  # needed to flush std to file
            "/flexric/build/examples/xApp/c/control/xapp_oran_slice_ctrl",
            "-c",
            config_file,
        )

        self._xapp_process_dict["rc_slice_xapp"] = self._executor.create_process(*cmd, logfile=logfile_descriptor)
        self._xapp_log_dict["rc_slice_xapp"] = logfile
        logging.info("RC slice xApp executed: %s, Logfile: %s", " ".join(cmd), logfile)
        return Empty()

    def StopRcXapp(self, request: Empty, context: grpc.ServicerContext) -> Empty:
        process = self._xapp_process_dict.pop("rc_slice_xapp", None)
        if process is not None and self._executor.is_process_alive(process):
            self._executor.exit_process(process)

        logfile = self._xapp_log_dict.pop("rc_slice_xapp", "")
        if logfile:
            text = ""
            with open(logfile, "r", encoding="UTF-8") as file:
                for line in file.readlines():
                    text += line.rstrip() + os.linesep

                nof_control_reqs = len(re.findall(r"CONTROL-REQUEST tx", text, flags=re.MULTILINE))
                nof_control_reps = len(re.findall(r"CONTROL ACK rx", text, flags=re.MULTILINE))

                logging.info("RC Slice xApp received: %i Control Acks", int(nof_control_reps))
                # collect stats for the final report
                self.ric_summary_report.nof_control_reqs += int(nof_control_reqs)
                self.ric_summary_report.nof_control_reps += int(nof_control_reps)

        return Empty()

    def GetNearRtRicSummary(self, request: Empty, context: grpc.ServicerContext) -> NearRtRicSummary:
        if self.ric_logfile:
            text = ""
            with open(self.ric_logfile, "r", encoding="UTF-8") as file:
                for line in file.readlines():
                    text += line.rstrip() + os.linesep

            nof_agents = len(re.findall(r"E2 SETUP-REQUEST rx", text, flags=re.MULTILINE))
            nof_xapps = len(re.findall(r" E42 SETUP-RESPONSE tx", text, flags=re.MULTILINE))
            logging.info("RIC: nof connected E2 agents: %i, nof connected xApps: %i", int(nof_agents), int(nof_xapps))

            self.ric_summary_report.nof_connected_agents += int(nof_agents)
            self.ric_summary_report.nof_connected_xapps += int(nof_xapps)

        return self.ric_summary_report

    @property
    def _expected_exit_code_array(self) -> Tuple[int, ...]:
        return (-9, -15, -137)

    @property
    def _warning_regex(self) -> str:
        return FLEXRIC_WARNING_HEADER + FLEXRIC_WARNING_BODY + FLEXRIC_WERROR_FOOTER

    @property
    def _error_regex(self) -> str:
        return FLEXRIC_ERROR_HEADER


FLEXRIC_ERROR_HEADER: str = r"^.*\[.*\[E\]"
FLEXRIC_WARNING_HEADER: str = r"^.*\[.*\[W\]"
FLEXRIC_WARNING_BODY: str = r"(?!.*Could not check scaling governor)" r"(?!.*ACK Wait Timeout)"
FLEXRIC_WERROR_FOOTER: str = r".*$"


class LocalFlexricRic(FlexricRic):
    """
    Flexric RIC Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
