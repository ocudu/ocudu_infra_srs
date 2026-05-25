# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Amarisoft 5GC Agent
"""

import ipaddress
import json
import logging
from contextlib import suppress
from typing import List, Type

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import (
    CoreMetrics,
    FiveGCDefinition,
    Metrics,
    PLMN,
    StopResponse,
    Subscriber,
    SubscriberArray,
)
from retina.protocol.fivegc_pb2 import FiveGCStartInfo

from retina.agent.drivers.amarisoft_ws import AmarisoftBaseDriver, AmarisoftWebSocket
from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.fivegc import FiveGCDriver
from retina.agent.features.executor import Executor, LocalExecutor, SshExecutor
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import fivegc_defaults, template_defaults, testbed_defaults
from retina.agent.templates import template_path
from retina.agent.tools.time import TimeoutHandler


class _AmarisoftMme(FiveGCDriver, AmarisoftBaseDriver):
    AMARISOFT_MME_CONF_FILE_BASE_NAME: str = "amarisoft_mme_base.cfg"
    AMARISOFT_MME_CONF_FILE_DATA_NAME: str = "amarisoft_mme_data.cfg"
    AMARISOFT_MME_CONF_FILE_FINAL_NAME: str = "amarisoft_mme.cfg"
    AMARISOFT_MME_LOG_FILENAME: str = "mme.log"
    AMARISOFT_MME_STDOUT_NAME: str = "stdout_mme"
    AMARISOFT_MME_TUN_SH = "amarisoft_mme_tun.sh"
    AMARISOFT_MME_START_TIMEOUT: int = 6
    _METRICS_ENCODING: str = "utf-8"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._subscriber_array: List[Subscriber] = []
        self._metrics = Metrics()

    def _get_binary_name(self) -> str:
        return "ltemme"

    def AddUESubscriber(self, request: Subscriber, context: grpc.ServicerContext) -> Empty:
        if request.imsi not in [my_sub.imsi for my_sub in self._subscriber_array]:
            self._subscriber_array.append(request)
        return Empty()

    def _get_tun_sh(self) -> str:
        return template_path(self.AMARISOFT_MME_TUN_SH)

    def Start(self, request: FiveGCStartInfo, context: grpc.ServicerContext) -> Empty:
        self.Stop(UInt32Value(value=request.start_info.timeout), context)

        mme_config_file = self._render(
            filename=self.AMARISOFT_MME_CONF_FILE_FINAL_NAME,
            templates={
                self.AMARISOFT_MME_CONF_FILE_BASE_NAME: template_defaults.main,
                self.AMARISOFT_MME_CONF_FILE_DATA_NAME: template_defaults.core,
            },
            prefix="{",
            suffix="\n}",
            values={
                **get_module_variables(testbed_defaults),
                **get_module_variables(fivegc_defaults),
                **self._get_log_variables(fivegc_defaults.log_level, self.AMARISOFT_MME_LOG_FILENAME),
                "subscriber_array": tuple(
                    sorted(
                        self._subscriber_array,
                        key=lambda item: item.imsi,
                    )
                ),
                "mcc": request.plmn.mcc,
                "mnc": request.plmn.mnc,
                "tun_sh_path": self._get_tun_sh(),
                "subnet_prefix": str(
                    ipaddress.ip_network(f"{fivegc_defaults.tun_subnet}/16", False).network_address
                ).replace(".0", ""),
            },
        )

        # Launch
        logfile = self.get_filepath_in_report_folder(self.AMARISOFT_MME_STDOUT_NAME + ".log")
        self._last_log_array = (logfile,)

        timeout_handler = TimeoutHandler(
            request.start_info.timeout if request.start_info.timeout else self.AMARISOFT_MME_START_TIMEOUT,
            msg="Amarisoft ltemme start timeout reached",
        )

        self.start_sut(
            *(item for pre_cmd in request.start_info.pre_commands for item in pre_cmd.split(" ")),
            self._get_binary_name(),
            "-S",
            str(1 / fivegc_defaults.time_multiplier),
            mme_config_file,
            *(item for post_cmd in request.start_info.post_commands for item in post_cmd.split(" ")),
            dryrun=request.start_info.dryrun,
            logfile=logfile,
            extra_env={"MME_TIME_MULTIPLIER": str(1 / fivegc_defaults.time_multiplier)},
        )

        if not request.start_info.dryrun:
            if not self._is_license_available(timeout_handler):
                request.start_info.timeout = int(timeout_handler.get_remaining_timeout())
                return self.Start(request, context)
        try:
            self._websocket = AmarisoftWebSocket()
        except (ConnectionRefusedError, ConnectionResetError) as err:
            raise ChildProcessError("Process has died") from err

        if not self._check_alive_thread.is_alive():
            raise ChildProcessError("Process has died")

        return Empty()

    def Stop(self, request: UInt32Value, context: grpc.ServicerContext) -> StopResponse:
        with suppress(AttributeError):
            stats = self._websocket.send_command_and_wait_response(message="stats", samples=False, rf=False)
            self._websocket.quit()
            # Save metrics into file
            if stats:
                with open(
                    self.get_filepath_in_report_folder(fivegc_defaults.metrics_filename_json),
                    "a+",
                    encoding=self._METRICS_ENCODING,
                ) as fd:
                    fd.write("[")
                    fd.write(json.dumps(stats))
                    fd.write("]")
                    fd.flush()
            # Generate gRPC metrics
            counters = stats.get("counters", {}).get("messages", {})
            self._metrics = Metrics(
                core=CoreMetrics(
                    nof_pdu_session_establishment_accept=counters.get("5gs_nas_pdu_session_establishment_accept", 0),
                    nof_pdu_session_modification_complete=counters.get("5gs_nas_pdu_session_modification_complete", 0),
                    nof_nas_service_accept=counters.get("5gs_nas_service_accept", 0),
                    nof_ng_paging=counters.get("ng_paging", 0),
                )
            )
        return super().Stop(request, context)

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        metrics = super().GetMetrics(request, context)
        metrics.MergeFrom(self._metrics)
        return metrics

    @property
    def _warning_regex(self) -> str:
        return r"^.*Warning(?!.*unused property)(?!.*buffer set to).*$"

    @property
    def _error_regex(self) -> str:
        return r"^.*(?:Error).*$"


class _RemoteAmarisoftMme(_AmarisoftMme):
    def start_sut(self, *args, **kwargs) -> None:
        self._kill_existing_lte()
        return super().start_sut(*args, **kwargs)

    def _get_tun_sh(self) -> str:
        remote_tun_sh = str(self._get_amarisoft_folder().joinpath(self.AMARISOFT_MME_TUN_SH))
        self._executor.copy_file(template_path(self.AMARISOFT_MME_TUN_SH), remote_tun_sh)
        return remote_tun_sh


class _AmarisoftIms(FiveGCDriver, AmarisoftBaseDriver):
    AMARISOFT_IMS_CONF_FILE_BASE_NAME: str = "amarisoft_ims.cfg"
    AMARISOFT_IMS_LOG_FILENAME: str = "ims.log"
    AMARISOFT_IMS_STDOUT_NAME: str = "stdout_ims"
    AMARISOFT_IMS_START_TIMEOUT: int = 6

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._plmn = PLMN()
        self._subscriber_array: List[Subscriber] = []

    def _get_binary_name(self) -> str:
        return "lteims"

    def AddUESubscriber(self, request: Subscriber, context: grpc.ServicerContext) -> Empty:
        if request.imsi not in [my_sub.imsi for my_sub in self._subscriber_array]:
            self._subscriber_array.append(request)
        return Empty()

    def Start(self, request: FiveGCStartInfo, context: grpc.ServicerContext) -> Empty:
        self.Stop(UInt32Value(value=request.start_info.timeout), context)
        self._plmn = request.plmn

        ims_config_file = self._render(
            filename=self.AMARISOFT_IMS_CONF_FILE_BASE_NAME,
            templates={self.AMARISOFT_IMS_CONF_FILE_BASE_NAME: template_defaults.ims},
            values={
                **get_module_variables(testbed_defaults),
                **get_module_variables(fivegc_defaults),
                **self._get_log_variables(fivegc_defaults.log_level, self.AMARISOFT_IMS_LOG_FILENAME),
                "subscriber_array": tuple(
                    sorted(
                        self._subscriber_array,
                        key=lambda item: item.imsi,
                    )
                ),
                "mcc": self._plmn.mcc,
                "mnc": self._plmn.mnc,
                "subnet_prefix": str(
                    ipaddress.ip_network(f"{fivegc_defaults.tun_subnet}/16", False).network_address
                ).replace(".0", ""),
            },
        )

        # Launch
        logfile = self.get_filepath_in_report_folder(self.AMARISOFT_IMS_STDOUT_NAME + ".log")
        self._last_log_array = (logfile,)

        timeout_handler = TimeoutHandler(
            request.start_info.timeout if request.start_info.timeout else self.AMARISOFT_IMS_START_TIMEOUT,
            msg="Amarisoft lteims start timeout reached",
        )

        self.start_sut(
            *(item for pre_cmd in request.start_info.pre_commands for item in pre_cmd.split(" ")),
            self._get_binary_name(),
            ims_config_file,
            *(item for post_cmd in request.start_info.post_commands for item in post_cmd.split(" ")),
            dryrun=request.start_info.dryrun,
            logfile=logfile,
        )

        if not request.start_info.dryrun:
            if not self._is_license_available(timeout_handler):
                request.start_info.timeout = int(timeout_handler.get_remaining_timeout())
                return self.Start(request, context)
        try:
            self._websocket = AmarisoftWebSocket()
        except (ConnectionRefusedError, ConnectionResetError) as err:
            raise ChildProcessError("Process has died") from err

        if not self._check_alive_thread.is_alive():
            raise ChildProcessError("Process has died")

        return Empty()

    def Stop(self, request: UInt32Value, context: grpc.ServicerContext) -> StopResponse:
        with suppress(AttributeError):
            self._websocket.quit()
        return super().Stop(request, context)

    def GetImsRegisteredUESubscriberArray(self, request: Empty, context: grpc.ServicerContext) -> SubscriberArray:
        impi_subscriber_dict = {
            f"{subscriber.imsi}@ims.mnc0{self._plmn.mnc}.mcc{self._plmn.mcc}.3gppnetwork.org": subscriber
            for subscriber in self._subscriber_array
        }

        result = super().GetImsRegisteredUESubscriberArray(request, context)
        for user in self._websocket.send_command_and_wait_response(message="users_get", registered_only=True).get(
            "users", tuple()
        ):
            if user["impi"] in impi_subscriber_dict:
                result.value.append(impi_subscriber_dict[user["impi"]])
        return result


class _RemoteAmarisoftIms(_AmarisoftIms):
    pass


class Amarisoft5gc(FiveGCDriver):
    """
    Amarisoft 5GC Agent
    """

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    def __init__(
        self,
        *args,
        report_folder: str,
        resource_folder: str,
        executor: Executor,
        ims_cls: Type[_AmarisoftIms],
        mme_cls: Type[_AmarisoftMme],
        **kwargs,
    ) -> None:
        super().__init__(
            *args, report_folder=report_folder, resource_folder=resource_folder, executor=executor, **kwargs
        )
        self._mme = mme_cls(
            *args, report_folder=report_folder + "/mme", resource_folder=resource_folder, executor=executor, *kwargs
        )
        self._ims = ims_cls(
            *args, report_folder=report_folder + "/ims", resource_folder=resource_folder, executor=executor, *kwargs
        )

    def _get_sut_version(self) -> str:
        return ""

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> FiveGCDefinition:
        definition = super().GetDefinition(request, context)
        if fivegc_defaults.ims_mode:
            definition.tun_ip = (
                str(ipaddress.ip_network(f"{fivegc_defaults.tun_subnet}/16", False).network_address).replace(".0", "")
                + ".4.1"
            )
            logging.info("IMS network enabled")
        else:
            definition.tun_ip = (
                str(ipaddress.ip_network(f"{fivegc_defaults.tun_subnet}/16", False).network_address).replace(".0", "")
                + ".32.1"
            )
        return definition

    def AddUESubscriber(self, request: Subscriber, context: grpc.ServicerContext) -> Empty:
        self._mme.AddUESubscriber(request, context)
        if fivegc_defaults.ims_mode == "enabled":
            self._ims.AddUESubscriber(request, context)
        return Empty()

    def GetImsRegisteredUESubscriberArray(self, request: Empty, context: grpc.ServicerContext) -> SubscriberArray:
        if fivegc_defaults.ims_mode:
            return self._ims.GetImsRegisteredUESubscriberArray(request, context)
        return super().GetImsRegisteredUESubscriberArray(request, context)

    def Start(self, request: FiveGCStartInfo, context: grpc.ServicerContext) -> Empty:
        with notify_grpc_exception(context):
            self._mme.Start(request, context)
            if fivegc_defaults.ims_mode:
                testbed_defaults.api_port += 1
                self._ims.Start(request, context)
            return Empty()

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        return self._mme.GetMetrics(request, context)

    def Stop(self, request: UInt32Value, context: grpc.ServicerContext) -> StopResponse:
        ims_response = self._ims.Stop(request, context)
        mme_response = self._mme.Stop(request, context)
        return StopResponse(
            exit_code=mme_response.exit_code if mme_response.exit_code else ims_response.exit_code,
            error_count=mme_response.error_count + ims_response.error_count,
            error_msg=mme_response.error_msg if mme_response.error_msg else ims_response.error_msg,
            warning_count=mme_response.warning_count + ims_response.warning_count,
            warning_msg=mme_response.warning_msg if mme_response.warning_msg else ims_response.warning_msg,
        )


class LocalAmarisoft5gc(_AmarisoftMme):
    """
    AmarisoftMME 5GC Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())


class RemoteAmarisoft5gc(Amarisoft5gc):
    """
    AmarisoftMME 5GC Agent for remote execution
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, executor=SshExecutor(), ims_cls=_RemoteAmarisoftIms, mme_cls=_RemoteAmarisoftMme
        )

    def Start(self, request: FiveGCStartInfo, context: grpc.ServicerContext) -> Empty:
        # Remote Amarisoft MME/IMS must bind sockets on the callbox host, not on the Retina pod IP.
        testbed_defaults.ip = testbed_defaults.api_address
        return super().Start(request, context)

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> FiveGCDefinition:
        testbed_defaults.ip = testbed_defaults.amf_address
        return super().GetDefinition(request, context)
