# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
OCUDU CU Agent
"""

from typing import Any, Dict, Optional, Sequence

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import CUCPDefinition, FiveGCDefinition, Metrics, PLMN, StopResponse
from retina.protocol.gnb_pb2 import CUStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.gnb import CUDriver
from retina.agent.drivers.ocudu_cu_cp import OcuduCuCp
from retina.agent.drivers.ocudu_cu_up import OcuduCuUp
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cu_cp = OcuduCuCp(*args, **kwargs)
        self._cu_cp.get_current_report_folder = self.get_current_report_folder  # type: ignore[method-assign]
        self._cu_up = OcuduCuUp(*args, **kwargs)
        self._cu_up.get_current_report_folder = self.get_current_report_folder  # type: ignore[method-assign]

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

    def get_parameters(
        self,
        *,
        fivegc_definition: Sequence[FiveGCDefinition],
        plmn: PLMN,
        neighbor_cucp_definition: Sequence[CUCPDefinition] = (),
    ) -> Dict[str, Any]:
        """
        Return parameters for config templates
        """
        return {
            **self._cu_cp.get_parameters(
                fivegc_definition=fivegc_definition,
                plmn=plmn,
                neighbor_cucp_definition=neighbor_cucp_definition,
            ),
            **self._cu_up.get_parameters(
                cucp_definition=(self.GetDefinition(Empty(), None),),
                fivegc_definition=fivegc_definition,
            ),
        }

    def Start(self, request: CUStartInfo, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            self.Stop(UInt32Value(value=request.start_info.timeout), context)
            self.reset_pcap_metrics()

            cu_logfile = self.get_filepath_in_report_folder(self.CU_STDOUT_NAME) + ".log"
            self._last_log_array = (
                cu_logfile,
                self.get_filepath_in_report_folder(self.CU_LOG_FILENAME),
            )

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
                    "cucp_ip": testbed_defaults.ip,
                    "cuup_ip": testbed_defaults.ip,
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
                self.read_from_log(
                    (r"==== CU started ===",),
                    True,
                    timeout=request.start_info.timeout if request.start_info.timeout else self.CU_START_UP_TIMEOUT,
                )

        return Empty()

    def reset_pcap_metrics(self) -> None:
        """Reset metrics state at the start of a new test run."""
        self._cu_cp.reset_pcap_metrics()

    def get_metrics_parsing_arguments(self):
        """
        Get Arguments for metrics parsing. Needs to be called before stop
        """
        return self._cu_cp.get_metrics_parsing_arguments()

    def extract_metrics(self, *args):
        """
        Extract Metrics
        """
        self._cu_cp.extract_metrics(*args)

    def Stop(self, request: UInt32Value, context: Optional[grpc.ServicerContext]) -> StopResponse:
        pcap_args = self._cu_cp.get_metrics_parsing_arguments()
        response = super().Stop(request, context)
        self._cu_cp.extract_metrics(*pcap_args)
        return response

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        metrics = super().GetMetrics(request, context)
        metrics.MergeFrom(self._cu_cp.GetMetrics(request, context))
        return metrics

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
