#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
SrsCuDu Agent
"""

import ipaddress

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import Metrics, StartInfo, StopResponse
from retina.protocol.gnb_pb2 import CUStartInfo, DUStartInfo, GNBStartInfo

from retina.agent.drivers.gnb import GNBDriver
from retina.agent.drivers.srs_cu import SrsCu
from retina.agent.drivers.srs_du import SrsDu
from retina.agent.features.executor import Executor, LocalExecutor
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.parameters import gnb_defaults, testbed_defaults


class SrsCuDu(GNBDriver, BaseDriverSutHandler):
    """
    SrsCuDu Agent
    """

    CU_DU_NETWORK = "127.0.10.1"

    def __init__(self, *args, report_folder: str, resource_folder: str, executor: Executor, **kwargs) -> None:
        super().__init__(
            *args, report_folder=report_folder, resource_folder=resource_folder, executor=executor, **kwargs
        )
        self._cu = SrsCu(
            *args, report_folder=report_folder + "/cu", resource_folder=resource_folder, executor=executor, *kwargs
        )
        self._du = SrsDu(
            *args, report_folder=report_folder + "/du", resource_folder=resource_folder, executor=executor, *kwargs
        )

    def _get_sut_version(self) -> str:
        return ""

    # pylint: disable=too-many-locals
    def Start(self, request: GNBStartInfo, context: grpc.ServicerContext) -> Empty:
        # Split Commands
        if len(request.start_info.pre_commands) == 2:
            cu_pre_str, du_pre_str = request.start_info.pre_commands
            cu_pre = [cu_pre_str]
            du_pre = [du_pre_str]
        else:
            cu_pre = du_pre = request.start_info.pre_commands
        if len(request.start_info.post_commands) == 2:
            cu_post_str, du_post_str = request.start_info.post_commands
            cu_post = [cu_post_str]
            du_post = [du_post_str]
        else:
            cu_post = du_post = request.start_info.post_commands

        # Internal subnet for CU/DU comm
        cu_ipaddress = ipaddress.ip_network(self.CU_DU_NETWORK, False).network_address
        du_ipaddress = cu_ipaddress + 1

        # Start CU
        gnb_defaults.cu_ip = str(cu_ipaddress)  # This is the trick to use a cu_ip different from the testbed ip
        cu_def = self._cu.GetDefinition(Empty(), context)  # it will have the custom cu_ip to use later in the du
        self._cu.Start(
            CUStartInfo(
                plmn=request.plmn,
                fivegc_definition=request.fivegc_definition,
                start_info=StartInfo(
                    dryrun=request.start_info.dryrun,
                    timeout=request.start_info.timeout,
                    pre_commands=cu_pre,
                    post_commands=cu_post,
                ),
            ),
            context,
        )
        gnb_defaults.cu_ip = ""

        # Start DU
        original_ip = testbed_defaults.ip
        testbed_defaults.ip = str(du_ipaddress)
        response = self._du.Start(
            DUStartInfo(
                gnb_du_id=gnb_defaults.gnb_du_id,
                plmn=request.plmn,
                num_cells=gnb_defaults.num_cells,
                cu_definition=cu_def,
                ue_definition=request.ue_definition,
                ric_definition=request.ric_definition,
                start_info=StartInfo(
                    dryrun=request.start_info.dryrun,
                    timeout=request.start_info.timeout,
                    pre_commands=du_pre,
                    post_commands=du_post,
                ),
            ),
            context,
        )
        testbed_defaults.ip = original_ip
        return response

    def Stop(self, request: UInt32Value, context: grpc.ServicerContext) -> StopResponse:
        du_response = self._du.Stop(request, context)
        cu_response = self._cu.Stop(request, context)
        return StopResponse(
            exit_code=cu_response.exit_code if cu_response.exit_code else du_response.exit_code,
            error_count=cu_response.error_count + du_response.error_count,
            error_msg=cu_response.error_msg if cu_response.error_msg else du_response.error_msg,
            warning_count=cu_response.warning_count + du_response.warning_count,
            warning_msg=cu_response.warning_msg if cu_response.warning_msg else du_response.warning_msg,
        )

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        return self._du.GetMetrics(request, context)


class LocalSrsCuDu(SrsCuDu):
    """
    SrsCuDu Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
