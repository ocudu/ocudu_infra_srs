#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
OCUDU gNB Agent
"""

import logging
from dataclasses import dataclass

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import Metrics, StopResponse
from retina.protocol.gnb_pb2 import GNBStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.gnb import GNBDriver
from retina.agent.drivers.ocudu_cu import OCUDU_CU_WARNING_BODY, OcuduCu
from retina.agent.drivers.ocudu_du import (
    OCUDU_DU_WARNING_BODY,
    OCUDU_ERROR_HEADER,
    OCUDU_WARNING_HEADER,
    OCUDU_WERROR_FOOTER,
    OcuduDu,
    RTSAN_ERROR,
)
from retina.agent.features.executor import LocalExecutor, SshExecutor
from retina.agent.features.gnb_report import transform_metrics
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import gnb_defaults, template_defaults, testbed_defaults


def trim_ru_port_list(port_id_str: str, num_ports: int) -> str:
    """
    Utility function which trims default tetbed ports to match number of configured antennas.
    """
    ports = [int(p.strip()) for p in port_id_str.strip("[]").split(",")]
    return str(ports[:num_ports])


# pylint: disable=too-many-instance-attributes
@dataclass
class _OFHRUInfo:
    network_interface: str = ""
    ru_mac_addr: str = ""
    du_mac_addr: str = ""
    vlan_tag_cp: str = ""
    vlan_tag_up: str = ""
    prach_port_id: str = ""
    dl_port_id: str = ""
    ul_port_id: str = ""


class OcuduGnb(GNBDriver, BaseDriverSutHandler):
    """
    OCUDU gNB Agent
    """

    GNB_BINARY_NAME: str = "gnb"
    GNB_STDOUT_NAME: str = "stdout"
    GNB_LOG_FILENAME: str = "gnb.log"
    GNB_CONF_FINAL_NAME: str = "ocudu_gnb.yml"
    GNB_CONF_MAIN_NAME: str = "ocudu_gnb_base.yml"
    GNB_CONF_AMF_NAME: str = "ocudu_gnb_amf.yml"
    GNB_CONF_CU_NAME: str = "ocudu_gnb_cu.yml"
    GNB_CONF_DU_NAME: str = "ocudu_gnb_du.yml"
    GNB_CONF_RU_NAME: str = "ocudu_gnb_ru.yml"
    GNB_CONF_QOS_NAME: str = "ocudu_gnb_qos.yml"
    GNB_CONF_METRICS_NAME: str = "ocudu_gnb_metrics.yml"
    GNB_START_UP_TIMEOUT: int = 5
    GNB_VERSION_REGEX: str = r"(\d+\.\d+(?:\.\d+)? \(\w+\))"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cu = OcuduCu(*args, **kwargs)
        self._du = OcuduDu(*args, **kwargs)

    def _get_sut_version(self) -> str:
        output = tuple(
            self._executor.run_binary(
                self.GNB_BINARY_NAME,
                "-v",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        version: str = self._parse_sut_version(output, self.GNB_VERSION_REGEX)
        return version

    def Start(self, request: GNBStartInfo, context: grpc.ServicerContext) -> Empty:
        self.Stop(UInt32Value(value=request.start_info.timeout), context)

        self._cu.set_current_report_folder(self.get_current_report_folder())
        self._du.set_current_report_folder(self.get_current_report_folder())

        if testbed_defaults.type == "ru":
            if not (
                len(testbed_defaults.ru_network_interface)
                == len(testbed_defaults.ru_du_mac_addr)
                == len(testbed_defaults.ru_ru_mac_addr)
                == len(testbed_defaults.ru_vlan_tag_cp)
                == len(testbed_defaults.ru_vlan_tag_up)
            ):
                logging.warning("Incorrect config: RU OFH properties in the testbed should have the same size")
                raise ValueError("The gNB agent can't be started due to incorrect testbed parameters")

            if gnb_defaults.num_cells > len(testbed_defaults.ru_network_interface):
                logging.warning(
                    "Incorrect config: the testbed RU doesn't support requested number of DU cells %s",
                    gnb_defaults.num_cells,
                )
                raise ValueError("The gNB agent can't be started due to incorrect DU config")

        gnb_conf_file = self._render(
            filename=self.GNB_CONF_FINAL_NAME,
            templates={
                self.GNB_CONF_AMF_NAME: "",
                self.GNB_CONF_METRICS_NAME: "",
                self.GNB_CONF_MAIN_NAME: template_defaults.main,
                self.GNB_CONF_CU_NAME: template_defaults.cu,
                self.GNB_CONF_DU_NAME: template_defaults.du,
                self.GNB_CONF_RU_NAME: template_defaults.ru,
                self.GNB_CONF_QOS_NAME: template_defaults.qos,
            },
            values={
                **get_module_variables(testbed_defaults),
                **get_module_variables(gnb_defaults),
                **self._cu.get_parameters(fivegc_definition=request.fivegc_definition, plmn=request.plmn),
                **self._du.get_parameters(
                    ue_definition=request.ue_definition,
                    gnb_du_id=gnb_defaults.gnb_du_id,
                    plmn=request.plmn,
                    num_cells=gnb_defaults.num_cells,
                    cell_offset=gnb_defaults.cell_offset,
                    ric_definition=request.ric_definition,
                ),
                "log_filename": self.get_filepath_in_report_folder(self.GNB_LOG_FILENAME),
                "ru_ofh_cells": tuple(
                    _OFHRUInfo(
                        network_interface=testbed_defaults.ru_network_interface[i],
                        ru_mac_addr=testbed_defaults.ru_ru_mac_addr[i],
                        du_mac_addr=testbed_defaults.ru_du_mac_addr[i],
                        vlan_tag_cp=testbed_defaults.ru_vlan_tag_cp[i],
                        vlan_tag_up=testbed_defaults.ru_vlan_tag_up[i],
                        prach_port_id=trim_ru_port_list(
                            testbed_defaults.ru_prach_port_id, gnb_defaults.nof_antennas_ul
                        ),
                        dl_port_id=trim_ru_port_list(testbed_defaults.ru_dl_port_id, gnb_defaults.nof_antennas_dl),
                        ul_port_id=trim_ru_port_list(testbed_defaults.ru_ul_port_id, gnb_defaults.nof_antennas_ul),
                    )
                    for i in range(gnb_defaults.num_cells if testbed_defaults.type == "ru" else 0)
                ),
            },
        )
        gnb_logfile = self.get_filepath_in_report_folder(self.GNB_STDOUT_NAME) + ".log"
        self._last_log_array = (
            gnb_logfile,
            self.get_filepath_in_report_folder(self.GNB_LOG_FILENAME),
        )

        # Start GNB
        self.start_sut(
            *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
            self.GNB_BINARY_NAME,
            "-c",
            gnb_conf_file,
            *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
            logfile=gnb_logfile,
            dryrun=request.start_info.dryrun,
        )

        # Wait for GNB to start
        if not request.start_info.dryrun:
            with notify_grpc_exception(context):
                # There is no good way to check if the gnb has already started.
                # We look for those lines in the log during some timeout.
                # If not found, we check if it's still alive
                try:
                    self.read_from_log(
                        (
                            r"gNodeB started",
                            r"Lower PHY started successfully",
                            r"Cell pci=",
                        ),
                        True,
                        timeout=request.start_info.timeout if request.start_info.timeout else self.GNB_START_UP_TIMEOUT,
                    )
                except TimeoutError as err:
                    logging.warning("Timeout reached while looking for GNB starting reference.")
                    if not self._is_alive:
                        with notify_grpc_exception(context):
                            raise err from None

                self._du.start_listening_metrics()

        return Empty()

    def Stop(self, request: UInt32Value, context: grpc.ServicerContext) -> StopResponse:
        metrics_json_path = self._du.stop_listening_metrics()
        pcap_args = self._du.get_metrics_parsing_arguments()
        response = super().Stop(request, context)
        self._du.extract_metrics(*pcap_args)
        transform_metrics(metrics_json_path)
        return response

    @property
    def _warning_regex(self) -> str:
        return (
            OCUDU_WARNING_HEADER
            + OCUDU_CU_WARNING_BODY
            + OCUDU_DU_WARNING_BODY
            + gnb_defaults.warning_extra_regex
            + OCUDU_WERROR_FOOTER
        )

    @property
    def _error_regex(self) -> str:
        return r"(?:" + RTSAN_ERROR + ")|(?:" + OCUDU_ERROR_HEADER + OCUDU_WERROR_FOOTER + r")"

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        return self._du.GetMetrics(request, context)


class LocalOcuduGnb(OcuduGnb):
    """
    OCUDU gNB Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())


class RemoteOcuduGnb(OcuduGnb):
    """
    OCUDU gNB Agent for remote
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=SshExecutor())

    def _get_sut_version(self) -> str:
        return ""
