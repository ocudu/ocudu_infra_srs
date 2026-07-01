# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Handles CLI arguments
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any, Callable, Dict, Optional, OrderedDict, TypeVar

import yaml

from retina.client.core.artifact_port import ArtifactPort
from retina.client.core.configuration_port import ConfigurationPort
from retina.client.core.testbed_port import NodeInfo, TestbedPort
from retina.client.core.version_port import IncompatibleRetinaVersion, VersionPort
from retina.protocol import (
    CUClient,
    CUCPClient,
    CUUPClient,
    DUClient,
    FiveGCClient,
    GNBClient,
    NearRtRicClient,
    RanClient,
    UEClient,
)

_T = TypeVar("_T", bound=RanClient)


@dataclass(frozen=True)
class _CommandInputs:
    testbed_path: str
    config_path: Optional[str]
    report_folder: str


# pylint: disable=too-many-public-methods
class RetinaEntrypoint:
    """
    Handles CLI arguments
    """

    GET_ITEM_TIMEOUT: int = 60
    REGISTER_PARAM_ALL_ITEMS: str = "all"

    def __init__(
        self,
        testbed_service: TestbedPort,
        parameter_service: ConfigurationPort,
        artifact_service: ArtifactPort,
        version_service: VersionPort,
    ) -> None:
        self._testbed_service: TestbedPort = testbed_service
        self._configuration_service: ConfigurationPort = parameter_service
        self._artifact_service: ArtifactPort = artifact_service
        self._version_service: VersionPort = version_service
        self._report_folder: str

    def parse_cmd_inputs(self) -> None:
        """
        Parse cmd arguments, looking for the testbed definition file and
        creating the required clients.
        """
        cli_inputs = self._argument_parser()
        self.parse_testbed_file(cli_inputs.testbed_path)
        if cli_inputs.config_path is not None:
            self.parse_configuration_file(cli_inputs.config_path)
        self.set_report_folder(cli_inputs.report_folder)

    def _argument_parser(self) -> _CommandInputs:
        parser = argparse.ArgumentParser(description="Retina client")
        parser.add_argument(
            "--testbed",
            type=str,
            help="File with the testbed to use in this test",
            required=True,
        )
        parser.add_argument("--configuration", type=str, help="Configuration File", default=None)
        parser.add_argument("--report-folder", type=str, help="Report folder path", default=Path.cwd())
        known_args, unknown_args = parser.parse_known_args()

        testbed_path = str(Path(known_args.testbed).resolve())
        config_path = str(Path(known_args.configuration).resolve()) if known_args.configuration is not None else None
        report_folder = str(Path(known_args.report_folder).resolve())

        for item in unknown_args:
            param_long_name, value = item.split("=")
            kind, name, key = param_long_name.replace("--", "", 1).split(".", 2)
            self._configuration_service.register_parameter(
                kind,
                name if name.strip().lower() != self.REGISTER_PARAM_ALL_ITEMS else None,
                key,
                value,
            )

        return _CommandInputs(
            testbed_path=testbed_path,
            config_path=config_path,
            report_folder=report_folder,
        )

    @staticmethod
    def _load_yml_file(filename: str) -> Any:
        if not Path(filename).exists():
            raise FileNotFoundError(f"File {filename} doesn't exist.")

        with open(
            filename,
            encoding="utf-8",
        ) as file:
            return yaml.load(file, yaml.FullLoader)

    def parse_testbed_file(self, testbed_path: str) -> None:
        """
        Parse a testbed file.
        """
        return self.parse_testbed(self._load_yml_file(testbed_path))

    def get_testbed_info(self) -> Dict[str, OrderedDict[str, NodeInfo]]:
        """
        Get the testbed info
        """
        return self._testbed_service.get_testbed_info()

    def parse_testbed(self, testbed_info: Dict) -> None:
        """
        Parse a testbed python object
        """
        return self._testbed_service.validate_testbed(testbed_info)

    def parse_configuration_file(self, configuration_file_path: str) -> None:
        """
        Parse a configuration file
        """
        return self.parse_configuration(self._load_yml_file(configuration_file_path))

    def parse_configuration(self, configuration_info: Dict) -> None:
        """
        Parse a configuration python object
        """
        return self._configuration_service.validate_configuration(configuration_info)

    def set_report_folder(self, report_folder: str) -> None:
        """
        Set report folder
        """
        self._report_folder = report_folder

    def register_template(self, kind: str, name: Optional[str], key: str, value: Any) -> None:
        """
        Save a template template_name:path to later push it to the client
        """
        return self._configuration_service.register_template(kind, name, key, value)

    def register_parameter(self, kind: str, name: Optional[str], key: str, value: Any) -> None:
        """
        Save a parameter key:value to later push it to the client
        """
        return self._configuration_service.register_parameter(kind, name, key, value)

    def get_ue(self, *args, **kwargs) -> UEClient:
        """
        Return a UE stub in the specified index.
        If not exists, raises an Exception.
        If `push_config` is set, it will send the configured parameters to the client
        """
        return self._get_item(self._testbed_service.get_ue, *args, **kwargs)

    def get_gnb(self, *args, **kwargs) -> GNBClient:
        """
        Return a gnb stub in the specified index.
        If not exists, raises an Exception.
        If `push_config` is set, it will send the configured parameters to the client
        """
        return self._get_item(self._testbed_service.get_gnb, *args, **kwargs)

    def get_cu(self, *args, **kwargs) -> CUClient:
        """
        Return a cu stub in the specified index.
        If not exists, raises an Exception.
        If `push_config` is set, it will send the configured parameters to the client
        """
        return self._get_item(self._testbed_service.get_cu, *args, **kwargs)

    def get_cu_cp(self, *args, **kwargs) -> CUCPClient:
        """
        Return a cu-cp stub in the specified index.
        If not exists, raises an Exception.
        If `push_config` is set, it will send the configured parameters to the client
        """
        return self._get_item(self._testbed_service.get_cu_cp, *args, **kwargs)

    def get_cu_up(self, *args, **kwargs) -> CUUPClient:
        """
        Return a cu-up stub in the specified index.
        If not exists, raises an Exception.
        If `push_config` is set, it will send the configured parameters to the client
        """
        return self._get_item(self._testbed_service.get_cu_up, *args, **kwargs)

    def get_du(self, *args, **kwargs) -> DUClient:
        """
        Return a du stub in the specified index.
        If not exists, raises an Exception.
        If `push_config` is set, it will send the configured parameters to the client
        """
        return self._get_item(self._testbed_service.get_du, *args, **kwargs)

    def get_5gc(self, *args, **kwargs) -> FiveGCClient:
        """
        Return a 5gc stub in the specified index.
        If not exists, raises an Exception.
        If `push_config` is set, it will send the configured parameters to the client
        """
        return self._get_item(self._testbed_service.get_5gc, *args, **kwargs)

    def get_ric(self, *args, **kwargs) -> NearRtRicClient:
        """
        Return a RIC stub in the specified index.
        If not exists, raises an Exception.
        If `push_config` is set, it will send the configured parameters to the client
        """
        return self._get_item(self._testbed_service.get_ric, *args, **kwargs)

    def _get_item(
        self,
        get_fun: Callable[[int], _T],
        index: int = 0,
        push_config: bool = True,
        timeout: float = GET_ITEM_TIMEOUT,
    ) -> _T:
        client = get_fun(index)

        maximum_time = time() + timeout
        while True:
            try:
                self._version_service.validate_client_version(client)
                break
            except IncompatibleRetinaVersion as err:
                raise err.with_traceback(err.__traceback__)
            except Exception as err:  # pylint: disable=broad-except
                if time() >= maximum_time:
                    raise err.with_traceback(err.__traceback__)

        if push_config:
            self._configuration_service.push_client_config(client)

        return client

    def push_client_config(self, stub: RanClient) -> None:
        """
        Send configured parameters to the client's agent
        """
        return self._configuration_service.push_client_config(stub)

    def push_all_config(self) -> None:
        """
        Send all configured parameters to their agents
        """
        return self._configuration_service.push_all_config()

    def reset_all_config(self) -> None:
        """
        Clean up all related configuration / parameters info
        """
        return self._configuration_service.reset_all_config()

    def download_client_artifacts(self, stub: RanClient) -> None:
        """
        Download artifacts for the specified client
        """
        return self._artifact_service.download_client_artifacts(stub, self._report_folder)

    def download_all_artifacts(self) -> None:
        """
        Download all artifacts from agents in the test and save them in
        the report folder
        """
        return self._artifact_service.download_all_artifacts(self._report_folder)

    def close_client(self, stub: RanClient) -> None:
        """
        Close client for specified
        """
        return self._testbed_service.close_client(stub)

    def close_all(self) -> None:
        """
        Close all clients
        """
        return self._testbed_service.close_all()
