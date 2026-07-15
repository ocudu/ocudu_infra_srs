# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
OCUDU CU-UP Agent
"""

import socket
from typing import Any, Dict, Sequence

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import CUCPDefinition, FiveGCDefinition
from retina.protocol.gnb_pb2 import CUUPStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.gnb import CUUPDriver
from retina.agent.drivers.ocudu_du import (
    OCUDU_ERROR_HEADER,
    OCUDU_WARNING_HEADER,
    OCUDU_WERROR_FOOTER,
    RTSAN_ERROR,
)
from retina.agent.features.executor import LocalExecutor
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import gnb_defaults, template_defaults, testbed_defaults
from retina.agent.tools.time import TimeoutHandler


class OcuduCuUp(CUUPDriver, BaseDriverSutHandler):
    """
    OCUDU CU-UP Agent
    """

    CUUP_BINARY_NAME: str = "ocuup"
    CUUP_STDOUT_NAME: str = "stdout_cu_up"
    CUUP_LOG_FILENAME: str = "cu_up.log"
    CUUP_VERSION_REGEX: str = r"(\d+\.\d+(?:\.\d+)? \(\w+\))"
    CUUP_CONF_FINAL_NAME: str = "ocudu_cu_up.yml"
    CUUP_CONF_MAIN_NAME: str = "ocudu_gnb_base.yml"
    CUUP_START_UP_TIMEOUT: int = 5

    def _get_sut_version(self) -> str:
        output = tuple(
            self._executor.run_binary(
                self.CUUP_BINARY_NAME,
                "-v",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        return self._parse_sut_version(output, self.CUUP_VERSION_REGEX)

    def get_parameters(
        self,
        *,
        cucp_definition: Sequence[CUCPDefinition],
        fivegc_definition: Sequence[FiveGCDefinition],
    ) -> Dict[str, Any]:
        """
        Return parameters for config templates
        """
        return {
            "e1ap_filename": self.get_filepath_in_report_folder(gnb_defaults.e1ap_filename),
            "n3_filename": self.get_filepath_in_report_folder(gnb_defaults.n3_filename),
            "cucp_definition": list(cucp_definition),
            "fivegc_definition": list(fivegc_definition),
        }

    def Start(self, request: CUUPStartInfo, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            self.Stop(UInt32Value(value=request.start_info.timeout), context)

            cuup_logfile = self.get_filepath_in_report_folder(self.CUUP_STDOUT_NAME) + ".log"
            self._last_log_array = (
                cuup_logfile,
                self.get_filepath_in_report_folder(self.CUUP_LOG_FILENAME),
            )

            cuup_conf_file = self._render(
                filename=self.CUUP_CONF_FINAL_NAME,
                templates={
                    self.CUUP_CONF_MAIN_NAME: template_defaults.main,
                    "": template_defaults.cu,
                },
                values={
                    **get_module_variables(testbed_defaults),
                    **get_module_variables(gnb_defaults),
                    **self.get_parameters(
                        cucp_definition=list(request.cucp_definition),
                        fivegc_definition=list(request.fivegc_definition),
                    ),
                    "log_filename": self.get_filepath_in_report_folder(self.CUUP_LOG_FILENAME),
                    "cucp_ip": request.cucp_definition[0].cucp_ip,
                    "cuup_ip": testbed_defaults.ip,
                },
            )

            if not request.start_info.dryrun:
                timeout = request.start_info.timeout if request.start_info.timeout else self.CUUP_START_UP_TIMEOUT
                timeout_handler = TimeoutHandler(
                    timeout,
                    msg="Timeout reached while waiting for CU-CP to listen",
                )
                for cucp in request.cucp_definition:
                    if cucp.cucp_ip == testbed_defaults.ip:
                        continue
                    with notify_grpc_exception(context):
                        while timeout_handler.not_reached():
                            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                                if sock.connect_ex((cucp.cucp_ip, cucp.cucp_port)) == 0:
                                    break

            self.start_sut(
                *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
                self.CUUP_BINARY_NAME,
                "-c",
                cuup_conf_file,
                *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
                logfile=cuup_logfile,
                dryrun=request.start_info.dryrun,
            )

            if not request.start_info.dryrun:
                self.read_from_log(
                    (r"==== CU-UP started ===",),
                    True,
                    timeout=(request.start_info.timeout if request.start_info.timeout else self.CUUP_START_UP_TIMEOUT),
                )

        return Empty()

    @property
    def _warning_regex(self) -> str:
        return OCUDU_WARNING_HEADER + OCUDU_CU_UP_WARNING_BODY + OCUDU_WERROR_FOOTER

    @property
    def _error_regex(self) -> str:
        return r"(?:" + RTSAN_ERROR + ")|(?:" + OCUDU_ERROR_HEADER + OCUDU_WERROR_FOOTER + r")"


OCUDU_CU_UP_WARNING_BODY: str = (
    r"(?!.*Could not check scaling governor)"
    r"(?!.*Dropped GTP-U PDU, queue is full)"
    r"(?!.*no metrics will be reported as no layer was enabled)"
)


class LocalOcuduCuUp(OcuduCuUp):
    """
    OCUDU CU-UP Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
