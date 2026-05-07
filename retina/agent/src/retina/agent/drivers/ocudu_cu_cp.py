# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
OCUDU CU-CP Agent
"""

import socket
from typing import Any, Dict, Sequence

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import FiveGCDefinition, PLMN
from retina.protocol.gnb_pb2 import CUCPStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.gnb import CUCPDriver
from retina.agent.drivers.ocudu_du import (
    get_cell_array,
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


class OcuduCuCp(CUCPDriver, BaseDriverSutHandler):
    """
    OCUDU CU-CP Agent
    """

    CUCP_BINARY_NAME: str = "ocucp"
    CUCP_STDOUT_NAME: str = "stdout_cu_cp"
    CUCP_LOG_FILENAME: str = "cu_cp.log"
    CUCP_VERSION_REGEX: str = r"(\d+\.\d+(?:\.\d+)? \(\w+\))"
    CUCP_CONF_FINAL_NAME: str = "ocudu_cu_cp.yml"
    CUCP_CONF_MAIN_NAME: str = "ocudu_gnb_base.yml"
    CUCP_CONF_AMF_NAME: str = "ocudu_gnb_amf.yml"
    CUCP_START_UP_TIMEOUT: int = 5

    def _get_sut_version(self) -> str:
        output = tuple(
            self._executor.run_binary(
                self.CUCP_BINARY_NAME,
                "-v",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        return self._parse_sut_version(output, self.CUCP_VERSION_REGEX)

    def get_parameters(self, *, fivegc_definition: Sequence[FiveGCDefinition], plmn: PLMN) -> Dict[str, Any]:
        """
        Return parameters for config templates
        """
        return {
            "ngap_filename": self.get_filepath_in_report_folder(gnb_defaults.ngap_filename),
            "f1ap_filename": self.get_filepath_in_report_folder(gnb_defaults.f1ap_filename),
            "e1ap_filename": self.get_filepath_in_report_folder(gnb_defaults.e1ap_filename),
            "n3_filename": self.get_filepath_in_report_folder(gnb_defaults.n3_filename),
            "fivegc_definition": list(fivegc_definition),
            "cell_array": get_cell_array(num_cells=gnb_defaults.num_cells, cell_offset=gnb_defaults.cell_offset),
            "mcc": plmn.mcc,
            "mnc": plmn.mnc,
        }

    def Start(self, request: CUCPStartInfo, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            self.Stop(UInt32Value(value=request.start_info.timeout), context)

            cucp_logfile = self.get_filepath_in_report_folder(self.CUCP_STDOUT_NAME) + ".log"
            self._last_log_array = (
                cucp_logfile,
                self.get_filepath_in_report_folder(self.CUCP_LOG_FILENAME),
            )

            cucp_def = self.GetDefinition(Empty(), context)

            cucp_conf_file = self._render(
                filename=self.CUCP_CONF_FINAL_NAME,
                templates={
                    self.CUCP_CONF_MAIN_NAME: template_defaults.main,
                    "": template_defaults.cu,
                    self.CUCP_CONF_AMF_NAME: "",
                },
                values={
                    **get_module_variables(testbed_defaults),
                    **get_module_variables(gnb_defaults),
                    **self.get_parameters(fivegc_definition=list(request.fivegc_definition), plmn=request.plmn),
                    "log_filename": self.get_filepath_in_report_folder(self.CUCP_LOG_FILENAME),
                    "cucp_ip": testbed_defaults.ip,
                },
            )

            self.start_sut(
                *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
                self.CUCP_BINARY_NAME,
                "-c",
                cucp_conf_file,
                *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
                logfile=cucp_logfile,
                dryrun=request.start_info.dryrun,
            )

            if not request.start_info.dryrun:
                with notify_grpc_exception(context):
                    timeout = request.start_info.timeout if request.start_info.timeout else self.CUCP_START_UP_TIMEOUT
                    timeout_handler = TimeoutHandler(
                        timeout,
                        msg="Timeout reached while waiting for CU-CP to listen in "
                        f"{cucp_def.cucp_ip}:{cucp_def.cucp_port}.",
                    )
                    while timeout_handler.not_reached():
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                            if sock.connect_ex((cucp_def.cucp_ip, cucp_def.cucp_port)) == 0:
                                break

        return Empty()

    @property
    def _warning_regex(self) -> str:
        return OCUDU_WARNING_HEADER + OCUDU_CU_CP_WARNING_BODY + OCUDU_WERROR_FOOTER

    @property
    def _error_regex(self) -> str:
        return r"(?:" + RTSAN_ERROR + ")|(?:" + OCUDU_ERROR_HEADER + OCUDU_WERROR_FOOTER + r")"


OCUDU_CU_CP_WARNING_BODY: str = (
    r"(?!.*Could not check scaling governor)"
    r"(?!.*Dropping UeContextReleaseCommand. UE does not exist)"
    r"(?!.*no metrics will be reported as no layer was enabled)"
)


class LocalOcuduCuCp(OcuduCuCp):
    """
    OCUDU CU-CP Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
