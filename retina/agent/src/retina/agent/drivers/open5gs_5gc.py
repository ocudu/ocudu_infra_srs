# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Open5gs 5GC Agent
"""

import ipaddress
from contextlib import contextmanager
from typing import Any, Dict, Generator, Tuple

import grpc
from bson.int64 import Int64
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from pymongo import MongoClient
from pymongo.collection import Collection
from retina.protocol.base_pb2 import Subscriber
from retina.protocol.fivegc_pb2 import FiveGCStartInfo

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.fivegc import FiveGCDriver
from retina.agent.features.executor import LocalExecutor
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import fivegc_defaults, template_defaults, testbed_defaults
from retina.agent.tools.time import TimeoutHandler


class Open5gs5gc(FiveGCDriver, BaseDriverSutHandler):
    """
    Open5gs 5GC Agent
    """

    OPEN5G_BINARY_NAME: str = "5gc"
    OPEN5G_STDOUT_NAME: str = "stdout"
    OPEN5G_CONF_FILE_BASE_NAME: str = "open5gs_5gc.yaml"
    OPEN5G_START_UP_TIMEOUT: int = 3
    OPEN5G_VERSION_REGEX: str = r"Open5GS v(\d+\.\d+(?:\.\d+)?)"

    _UE_IP_OFFSET_START: int = 2
    _UE_IP_OFFSET_INTERVAL: int = 256

    # Open5gs uses the SQN stored in the database for the current authentication vector and only increments it
    # afterwards. Leaving it unset makes the first Authentication Request carry SQN=0, which a USIM whose SQN_MS is
    # also 0 must reject with a synch failure (3GPP TS 33.102 Annex C.2). Seeding it with the open5gs SQN step avoids
    # the resynchronization round trip and the warnings it logs. Open5gs only reads the field if it is a BSON int64.
    _SUBSCRIBER_SQN: Int64 = Int64(32)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ue_ip_offset: int = self._UE_IP_OFFSET_START

    def _get_sut_version(self) -> str:
        output = tuple(
            self._executor.run_binary(
                self.OPEN5G_BINARY_NAME,
                "-v",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        version: str = self._parse_sut_version(output, self.OPEN5G_VERSION_REGEX)
        return version

    def Start(self, request: FiveGCStartInfo, context: grpc.ServicerContext) -> Empty:
        self.Stop(UInt32Value(value=request.start_info.timeout), context)

        with notify_grpc_exception(context):
            if fivegc_defaults.time_multiplier != 1:
                raise ValueError("Open5gs doesn't support time simulation")

        config_file = self._render(
            filename=self.OPEN5G_CONF_FILE_BASE_NAME,
            templates={self.OPEN5G_CONF_FILE_BASE_NAME: template_defaults.main},
            values={
                "mcc": request.plmn.mcc,
                "mnc": request.plmn.mnc,
                **get_module_variables(testbed_defaults),
                **get_module_variables(fivegc_defaults),
                "log_level": {"warning": "warn"}.get(fivegc_defaults.log_level, fivegc_defaults.log_level),
            },
        )

        # Launch

        logfile = self.get_filepath_in_report_folder(self.OPEN5G_STDOUT_NAME) + ".log"
        self._last_log_array = (logfile,)

        self._ue_ip_offset = self._UE_IP_OFFSET_START
        self.start_sut(
            *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
            self.OPEN5G_BINARY_NAME,
            "-c",
            config_file,
            *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
            dryrun=request.start_info.dryrun,
            logfile=logfile,
        )

        # Wait until udr is up and running
        if not request.start_info.dryrun:
            with notify_grpc_exception(context):
                timeout = request.start_info.timeout if request.start_info.timeout else self.OPEN5G_START_UP_TIMEOUT
                timeout_handler = TimeoutHandler(timeout)
                while timeout_handler.not_reached():
                    if self._port_in_use(fivegc_defaults.udr_port, fivegc_defaults.udr_ip):
                        break

        return Empty()

    @property
    def _warning_regex(self) -> str:
        return (
            r"^.*\[1;36mWARNING\x1B\[0m: "
            r"(?!.*Please change the configuration files)"
            r"(?!.*NF has already been added)"
            r"(?!.*UnRef NF EndPoint)"
            r"(?!.*Couldn't connect to server)"
            r"(?!.*Could not connect to server)"
            r"(?!.*ogs_sbi_client_handler\(\) failed)"
            r"(?!.*Failed sending data to the peer)"
            r"(?!.*Cause\[Group:)"
            r"(?!.*NGReset)"
            r"(?!.*NGAP_ResetType_PR_)"
            r".*$"
        )

    @property
    def _error_regex(self) -> str:
        return (
            r"^.*\[1;33mERROR\x1B\[0m: "
            r"(?!.*Child status change)"
            r"(?!.*Invalid packet)"
            r"(?!.*No IPv6 subnet)"
            r"(?!.*Send Error Indication)"
            r"(?!.*Cannot find PDU Session ID)"
            r"(?!.*Failed to find RAN UE by NGAP UE IDs)"
            r"(?!.*No RAN UE Context)"
            r"(?!.*No NF-Instance)"
            r"(?!.*HTTP response error)"
            r".*$"
        )

    @property
    def _exit_children_first(self) -> bool:
        return True

    def AddUESubscriber(self, request: Subscriber, context: grpc.ServicerContext) -> Empty:
        # For each UE, we assign it an IP in another subnet FIX.FIX.z.1
        ue_ip = str(
            (
                ipaddress.ip_network(f"{fivegc_defaults.tun_subnet}/{fivegc_defaults.tun_mask}", False).network_address
                + self._ue_ip_offset
            )
        )
        self._ue_ip_offset += self._UE_IP_OFFSET_INTERVAL
        sub_data: Dict[str, Any] = {
            "imsi": request.imsi,
            "subscribed_rau_tau_timer": 12,
            "network_access_mode": 2,
            "subscriber_status": 0,
            "access_restriction_data": 32,
            "slice": [
                {
                    "sst": 1,
                    "default_indicator": True,
                    "session": [
                        {
                            "name": fivegc_defaults.apn,
                            "type": 3,
                            "pcc_rule": [],
                            "ambr": {
                                "uplink": {"value": 1, "unit": 3},
                                "downlink": {"value": 1, "unit": 3},
                            },
                            "qos": {
                                "index": 9,
                                "arp": {
                                    "priority_level": 8,
                                    "pre_emption_capability": 1,
                                    "pre_emption_vulnerability": 1,
                                },
                            },
                            "ue": {
                                "ipv4": ue_ip,
                            },
                        }
                    ],
                }
            ],
            "ambr": {
                "uplink": {"value": 1, "unit": 3},
                "downlink": {"value": 1, "unit": 3},
            },
            "security": {
                "k": request.k,
                "amf": request.amf,
                "op": None,
                "opc": request.opc,
                "schema_version": 1,
                "__v": 0,
            },
        }

        if request.sd:
            sub_data["slice"][0]["sd"] = request.sd

        subscriber = Open5gsDB.get_subscriber(request.imsi)
        if subscriber is None:
            sub_data["security"]["sqn"] = self._SUBSCRIBER_SQN
            result = Open5gsDB.add_subscriber(sub_data) is not None
        else:
            # The whole security subdocument is overwritten, so carry over the SQN already reached by the subscriber
            sub_data["security"]["sqn"] = Int64(subscriber.get("security", {}).get("sqn", self._SUBSCRIBER_SQN))
            result = Open5gsDB.update_subscriber(request.imsi, sub_data) is not None

        if not result:
            raise ValueError("UE can't be added")

        return Empty()

    @property
    def _expected_exit_code_array(self) -> Tuple[int, ...]:
        return (-256,)


class LocalOpen5gs5gc(Open5gs5gc):
    """
    Open5gs 5GC Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())


class Open5gsDB:
    """
    Manager Open5gs DataBase
    """

    @staticmethod
    @contextmanager
    def _get_db_subscriber() -> Generator[Collection, None, None]:
        client: MongoClient = MongoClient("mongodb://" + fivegc_defaults.db_addr + "/")
        yield client["open5gs"]["subscribers"]
        client.close()

    @classmethod
    def get_subscriber(cls, imsi: str) -> Any:
        """
        Get a subscriber by imsi
        """
        with cls._get_db_subscriber() as subscribers:
            for item in subscribers.find({"imsi": str(imsi)}):
                return item
            return None

    @classmethod
    def update_subscriber(cls, imsi: str, sub_data: Dict) -> bool:
        """
        Update a subscriber
        """
        with cls._get_db_subscriber() as subscribers:
            return bool(subscribers.update_one({"imsi": str(imsi)}, {"$set": sub_data}).modified_count == 1)

    @classmethod
    def add_subscriber(cls, sub_data: Dict) -> Any:
        """
        Add a new subscriber
        """
        with cls._get_db_subscriber() as subscribers:
            return subscribers.insert_one(sub_data).inserted_id
