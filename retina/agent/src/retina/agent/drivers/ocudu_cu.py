# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
OCUDU CU Agent
"""

import socket
from typing import Any, Dict, Sequence

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import FiveGCDefinition, PLMN
from retina.protocol.gnb_pb2 import CUStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.gnb import CUDriver
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


class OcuduCu(CUDriver, BaseDriverSutHandler):
    """
    OCUDU CU Agent
    """

    CU_BINARY_NAME: str = "ocu"
    CU_STDOUT_NAME: str = "stdout_cu"
    CU_LOG_FILENAME: str = "cu.log"
    CU_VERSION_REGEX: str = r"(\d+\.\d+(?:\.\d+)? \(\w+\))"
    CU_CONF_FINAL_NAME: str = "ocudu_cu.yml"
    CU_CONF_MAIN_NAME: str = "ocudu_gnb_base.yml"
    CU_CONF_AMF_NAME: str = "ocudu_gnb_amf.yml"
    CU_CONF_CU_NAME: str = "ocudu_gnb_cu.yml"
    CU_CONF_QOS_NAME: str = "ocudu_gnb_qos.yml"
    CU_START_UP_TIMEOUT: int = 5

    def _get_sut_version(self) -> str:
        output = tuple(
            self._executor.run_binary(
                self.CU_BINARY_NAME,
                "-v",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        version: str = self._parse_sut_version(output, self.CU_VERSION_REGEX)
        return version

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
            "gnb_id": gnb_defaults.gnb_id,
            "gnb_id_bit_length": gnb_defaults.gnb_id_bit_length,
            "cell_array": get_cell_array(num_cells=gnb_defaults.num_cells, cell_offset=gnb_defaults.cell_offset),
            "mcc": plmn.mcc,
            "mnc": plmn.mnc,
        }

    def Start(self, request: CUStartInfo, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            self.Stop(UInt32Value(value=request.start_info.timeout), context)

            cu_logfile = self.get_filepath_in_report_folder(self.CU_STDOUT_NAME) + ".log"
            self._last_log_array = (
                cu_logfile,
                self.get_filepath_in_report_folder(self.CU_LOG_FILENAME),
            )

            cu_def = self.GetDefinition(Empty(), context)

            cu_conf_file = self._render(
                filename=self.CU_CONF_FINAL_NAME,
                templates={
                    self.CU_CONF_MAIN_NAME: template_defaults.main,
                    self.CU_CONF_CU_NAME: template_defaults.cu,
                    self.CU_CONF_QOS_NAME: template_defaults.qos,
                    self.CU_CONF_AMF_NAME: "",
                },
                values={
                    **get_module_variables(testbed_defaults),
                    **get_module_variables(gnb_defaults),
                    **self.get_parameters(fivegc_definition=list(request.fivegc_definition), plmn=request.plmn),
                    "log_filename": self.get_filepath_in_report_folder(self.CU_LOG_FILENAME),
                    "cu_ip": cu_def.cu_ip,
                },
            )

            # Launch CU binary
            self.start_sut(
                *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
                self.CU_BINARY_NAME,
                "-c",
                cu_conf_file,
                *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
                logfile=cu_logfile,
                dryrun=request.start_info.dryrun,
            )

            # Wait until CU has started
            if not request.start_info.dryrun:
                with notify_grpc_exception(context):
                    timeout = request.start_info.timeout if request.start_info.timeout else self.CU_START_UP_TIMEOUT
                    timeout_handler = TimeoutHandler(
                        timeout,
                        msg=f"Timeout reached while waiting for CU to listen in {cu_def.cu_ip}:{cu_def.cu_port}.",
                    )
                    while timeout_handler.not_reached():
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                            if sock.connect_ex((cu_def.cu_ip, cu_def.cu_port)) == 0:
                                break

        return Empty()

    @property
    def _warning_regex(self) -> str:
        return OCUDU_WARNING_HEADER + OCUDU_CU_WARNING_BODY + OCUDU_WERROR_FOOTER

    @property
    def _error_regex(self) -> str:
        return r"(?:" + RTSAN_ERROR + ")|(?:" + OCUDU_ERROR_HEADER + OCUDU_WERROR_FOOTER + r")"


OCUDU_CU_WARNING_BODY: str = (
    r"(?!.*Could not check scaling governor)"
    r"(?!.*Dropping UeContextReleaseCommand. UE does not exist)"
    r"(?!.*Dropped GTP-U PDU, queue is full)"
    r"(?!.*no metrics will be reported as no layer was enabled)"
)


class LocalOcuduCu(OcuduCu):
    """
    OCUDU CU Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
