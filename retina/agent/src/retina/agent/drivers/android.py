#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Android UE Agent
"""

import ipaddress
import logging
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Tuple

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import StopResponse
from retina.protocol.ue_pb2 import UEAttachedInfo, UEStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.ue import UEDriver
from retina.agent.features.executor import AdbExecutor, LocalExecutor
from retina.agent.parameters import testbed_defaults, ue_defaults


class AndroidUe(UEDriver):
    """
    Android UE Agent
    """

    AIRPLANE_MODE_SLEEP: float = 0.5
    CONNECTION_TIMEOUT: float = 20.0

    STATE_DICT: Dict[bool, str] = {False: "disable", True: "enable"}
    STATE_DICT_REV: Dict[str, bool] = {v: k for k, v in STATE_DICT.items()}

    @staticmethod
    def bool_to_state_str(state: bool) -> str:
        """
        Convert a bool into a state string "enable" or "disable"
        """
        return AndroidUe.STATE_DICT[state]

    @staticmethod
    def state_str_to_bool(state_str: str) -> bool:
        """
        Convert a state string "enable" or "disable" into a bool
        """
        return AndroidUe.STATE_DICT_REV[state_str]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._waiting_for_attach: bool = False
        self._wait_start_time: float = 0.0
        self._wait_timeout: float = 0.0
        self._5gc_ip: str
        self._5gc_mask: int
        self._device_found: bool = False

    def _get_sut_version(self) -> str:
        local_executor = LocalExecutor()
        output = tuple(
            local_executor.run_binary("adb", "version"),
        )
        return " ".join(output)

    def Stop(self, request: UInt32Value, context: Optional[grpc.ServicerContext]) -> StopResponse:
        self._stop_wait()
        if self._device_found:
            self._set_airplane_mode(True)
            time.sleep(self.AIRPLANE_MODE_SLEEP)
        return super().Stop(request, context)

    def Start(self, request: UEStartInfo, context: grpc.ServicerContext) -> Empty:
        self._find_device(context)
        self.Stop(UInt32Value(value=request.start_info.timeout), context)

        self._5gc_ip = request.fivegc_definition.tun_ip
        self._5gc_mask = request.fivegc_definition.tun_mask

        with notify_grpc_exception(context):
            self._set_airplane_mode(False)
            self._set_wifi_state(False)

        return Empty()

    def _find_device(self, context: grpc.ServicerContext) -> None:
        logging.debug("Find Android device with serial %s", testbed_defaults.serial_id)
        local_executor = LocalExecutor()
        found: bool = False
        for line in local_executor.run_binary("adb", "devices"):
            logging.debug(line)
            if line.find(testbed_defaults.serial_id) >= 0:
                found = True
        if not found:
            logging.error(
                "Could not find Android device with serial %s",
                testbed_defaults.serial_id,
            )
            with notify_grpc_exception(context):
                raise KeyError("Could not find Android device") from None
        self._device_found = True

    def _set_airplane_mode(self, apm_state: bool) -> None:
        tuple(
            self._executor.run_binary(
                "cmd",
                "connectivity",
                "airplane-mode",
                AndroidUe.bool_to_state_str(apm_state),
            )
        )

    def _set_wifi_state(self, wifi_state: bool) -> None:
        tuple(
            self._executor.run_binary(
                "svc",
                "wifi",
                AndroidUe.bool_to_state_str(wifi_state),
            )
        )

    def _set_apn(self):
        apn_params = defaultdict(
            lambda: "",
            {
                "carrier": ue_defaults.apn,
                "apn": ue_defaults.apn,
            },
        )

        carr_id = self._get_carrier_id(apn_params["carrier"])
        self._delete_carrier(apn_params["carrier"])
        self._add_carrier(apn_params)
        self._select_preferred_carrier(carr_id)

    def _get_carrier_id(self, carr_name: str) -> str:
        carr_id: Optional[str] = None
        for available_carrier in self._executor.run_binary('content query --uri "content://telephony/carriers"'):
            if "name=" + carr_name in available_carrier:
                carr_id = re.findall(r"_id=(\S+),", available_carrier)[0]
                break

        if carr_id is None:
            raise KeyError(f"Can not find apn {carr_name}")

        return carr_id

    def _delete_carrier(self, carr_name: str) -> None:
        """
        Delete it if exist to force a new connection
        """
        tuple(
            self._executor.run_binary(
                "content delete --uri content://telephony/carriers --where 'name=\"" + str(carr_name) + "\" '"
            )
        )

    def _add_carrier(self, apn_params: Dict[str, str]) -> None:
        tuple(
            self._executor.run_binary(
                "content insert --uri content://telephony/carriers"
                + ' --bind name:s:"'
                + apn_params["carrier"]
                + '"'
                + ' --bind numeric:s:"'
                + apn_params["mcc"]
                + apn_params["mnc"]
                + '"'
                + ' --bind mcc:s:"'
                + apn_params["mcc"]
                + '"'
                + ' --bind mnc:s:"'
                + apn_params["mnc"]
                + '"'
                + ' --bind apn:s:"'
                + apn_params["apn"]
                + '"'
                + ' --bind user:s:"'
                + apn_params["user"]
                + '"'
                + ' --bind password:s:"'
                + apn_params["password"]
                + '"'
                + ' --bind mmsc:s:"'
                + apn_params["mmsc"]
                + '"'
                + ' --bind mmsport:s:"'
                + apn_params["mmsport"]
                + '"'
                + ' --bind mmsproxy:s:"'
                + apn_params["mmsproxy"]
                + '"'
                + ' --bind authtype:s:"'
                + apn_params["auth"]
                + '"'
                + ' --bind type:s:"'
                + apn_params["type"]
                + '"'
                + ' --bind protocol:s:"'
                + apn_params["protocol"]
                + '"'
                + ' --bind mvno_type:s:"'
                + apn_params["mvnotype"]
                + '"'
                + ' --bind mvno_match_data:s:"'
                + apn_params["mvnoval"]
                + '"'
            )
        )

    def _select_preferred_carrier(self, carr_id: str) -> None:
        tuple(
            self._executor.run_binary(
                'content insert --uri content://telephony/carriers/preferapn --bind apn_id:s:"' + str(carr_id) + '"'
            )
        )

    def _is_attached(self) -> bool:
        for line in self._executor.run_binary("getprop", "gsm.network.type"):
            if any(rat in line for rat in ["NR_SA", "LTE_NR"]):
                return True
        return False

    def _has_ip(self) -> Tuple[bool, str, str]:
        for line in self._executor.run_binary("ip", "-4", "-brief", "addr", "show"):
            words = line.lstrip().split()
            ip_and_mask = words[2]
            ip_address = ip_and_mask.split("/")[0]
            if (
                ipaddress.ip_network(f"{ip_address}/{self._5gc_mask}", False).network_address
                == ipaddress.ip_network(f"{self._5gc_ip}/{self._5gc_mask}", False).network_address
            ):
                interface = words[0]
                return (True, interface, ip_address)
        return (False, "", "")

    def _has_route(self, dst_ip_address: str) -> bool:
        for line in self._executor.run_binary("ip", "route", "get", dst_ip_address):
            if "dev" in line and "src" in line:
                return True
        return False

    def _start_wait(self, timeout):
        self._waiting_for_attach = True
        self._wait_start_time = time.time()
        self._wait_timeout = timeout

    def _stop_wait(self):
        self._waiting_for_attach = False

    def _get_wait_time(self) -> float:
        return time.time() - self._wait_start_time

    def _continue_wait(self, throw_exception: bool = True) -> bool:
        if not self._waiting_for_attach:
            if throw_exception:
                raise InterruptedError("Interrupted wait.")
            return False
        if self._get_wait_time() >= self._wait_timeout:
            self._stop_wait()
            if throw_exception:
                raise TimeoutError(f"Timeout after {self._wait_timeout:.3f}s.")
            return False
        return True

    def WaitUntilAttached(self, request: UInt32Value, context: grpc.ServicerContext) -> UEAttachedInfo:
        self._start_wait(max(float(request.value), self.CONNECTION_TIMEOUT))

        with notify_grpc_exception(context):
            # Wait for connection to 5G network
            while not self._is_attached() and self._continue_wait():
                logging.info(
                    "Waiting for UE to attach. (%.3fs/%.3fs)",
                    self._get_wait_time(),
                    self._wait_timeout,
                )
            logging.info("UE attached. (%.3fs/%.3fs)", self._get_wait_time(), self._wait_timeout)

            # Wait for IP address
            has_ip = False
            while not has_ip and self._continue_wait():
                logging.info(
                    "Waiting for IP address. (%.3fs/%.3fs).",
                    self._get_wait_time(),
                    self._wait_timeout,
                )
                (has_ip, interface, ip_address) = self._has_ip()
            logging.info(
                "UE has IP address %s on interface %s. (%.3fs/%.3fs)",
                ip_address,
                interface,
                self._get_wait_time(),
                self._wait_timeout,
            )

            # Wait for route
            while not self._has_route(self._5gc_ip) and self._continue_wait():
                logging.info(
                    "Waiting for route. (%.3fs/%.3fs).",
                    self._get_wait_time(),
                    self._wait_timeout,
                )
            logging.info(
                "UE has route to %s via interface %s. (%.3fs/%.3fs)",
                self._5gc_ip,
                interface,
                self._get_wait_time(),
                self._wait_timeout,
            )

        # Success!
        self._stop_wait()
        return UEAttachedInfo(
            interface=interface,
            ipv4=ip_address,
            ipv4_gateway=str(ipaddress.ip_network(f"{self._5gc_ip}/{self._5gc_mask}", False).network_address + 1),
        )

    def _run_iperf(self, arg_dict: dict, timeout: float, context: grpc.ServicerContext):
        """
        Override of run_iperf function that also to downloads logfile from Android device
        """
        local_logfile = arg_dict["--logfile"]
        remote_logfile = str(Path("/data/local/tmp").joinpath(os.path.basename(local_logfile)))
        arg_dict["--logfile"] = remote_logfile
        super()._run_iperf(arg_dict, timeout, context)

        # download logfile
        local_executor = LocalExecutor()
        for line in local_executor.run_binary(
            "adb",
            "-s",
            testbed_defaults.serial_id,
            "pull",
            remote_logfile,
            local_logfile,
        ):
            logging.debug(line)

        # remove logfile from remote device
        for line in self._executor.run_binary(
            "rm",
            remote_logfile,
            keeplinebreaks=False,
            timeout=None,
            raise_if_exit_code=False,
        ):
            logging.debug(line)


class AdbAndroidUE(AndroidUe):
    """
    Android UE Agent using ADB
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=AdbExecutor())
