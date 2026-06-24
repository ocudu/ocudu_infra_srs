# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Command Line Arguments
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pytest
import yaml


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Retina arguments
    """
    # Pytest
    _add_cmd_and_ini(parser, "log_folder", default="./log", help="Retina Log folder")
    # Testbed definitions
    parser.addoption("--retina-request", default="", help="Retina request YAML.")
    parser.addoption("--retina-testbed", default="", help="Retina testbed YAML.")
    # Orchestration
    parser.addoption("--retina-orch-timeout", help="Retina Orchestration Timeout.")
    parser.addoption("--retina-in-cluster", default=False, action="store_true", help="Running inside a cluster.")
    # CLI Parameters
    parser.addoption(
        "--register-parameter",
        default=tuple(),
        nargs="*",
        help="Parameters pushed to the resources",
    )
    parser.addoption(
        "--register-template",
        default=tuple(),
        nargs="*",
        help="Templates pushed to the resources",
    )
    parser.addoption(
        "--force-download",
        default=False,
        action="store_true",
        help="Download artifacts even if the test passes",
    )
    # Graph
    _add_cmd_and_ini(
        parser,
        "graph_url",
        default="",
        help="Remote Visualization configuration in format my_url@org:my_token",
    )
    _add_cmd_and_ini(
        parser,
        "graph_bucket",
        default="",
        help="Remote Visualization bucket configuration",
    )


@dataclass
class RetinaRequest:
    """
    Request or Testbed
    """

    request: Optional[str] = None
    testbed: Optional[str] = None
    pod_timeout: Optional[int] = None
    in_cluster: bool = False


@pytest.fixture
def retina_request(request: pytest.FixtureRequest) -> RetinaRequest:
    """
    Test Request
    """

    req = RetinaRequest()
    retina_request_raw: str = request.config.getoption("retina_request")
    retina_testbed_raw: str = request.config.getoption("retina_testbed")

    req.pod_timeout = (
        int(request.config.getoption("retina_orch_timeout"))
        if request.config.getoption("retina_orch_timeout") is not None
        else None
    )
    req.in_cluster = request.config.getoption("retina_in_cluster")
    if req.in_cluster:
        logging.debug("Running in in_cluster mode")

    if retina_request_raw and retina_testbed_raw:
        retina_request_raw = ""
    if not retina_request_raw and not retina_testbed_raw:
        raise ValueError(
            "You need to specify ONE of the following: \n"
            + "- A request.yml file using --retina-request to deploy a testbed.\n"
            + "- A testbed.yml file using --retina-testbed to use an existing testbed."
        )

    if retina_request_raw:
        retina_request_path: Path = Path(retina_request_raw).resolve()
        if not retina_request_path.exists() and request.param is not None:
            retina_request_path = Path(request.param).resolve()
        if not retina_request_path.exists():
            raise ValueError(f"Specified retina request [{retina_request_path}] is not valid.")
        logging.debug("Request: %s", retina_request_path)
        req.request = str(retina_request_path)

    if retina_testbed_raw:
        retina_testbed_path: Path = Path(retina_testbed_raw).resolve()
        if not retina_testbed_path.exists():
            raise ValueError(f"Specified retina testbed [{retina_testbed_raw}] is not valid.")
        logging.debug("Testbed: %s", retina_testbed_path)
        req.testbed = str(retina_testbed_path)

    return req


PYTEST_SUITE_SEPARATOR: str = "::"


def get_folder_name(config: pytest.Config, nodeid: str) -> Path:
    """
    Return folder for each test
    """
    return Path(_get_cmd_and_ini(config, "log_folder")).joinpath(*nodeid.split(PYTEST_SUITE_SEPARATOR)).resolve()


@pytest.fixture
def test_log_folder(request: pytest.FixtureRequest) -> str:
    """
    Return folder for each test artifacts
    """
    # If we remove/clean the log_folder in a session fixture, we can't use xdist plugin
    # xdist plugin launch multiple python processes, so they can have conflicts when trying to delete
    #  or one can delete the log folder after the other
    # Cleaning the folder would be nice but it's not required because
    #  - report.html is generated every time
    #  - in retina fixture, we remove old test artifact folder
    test_log_folder_path = get_folder_name(request.config, request.node.nodeid)
    # We delete it first to avoid issues if already exists
    if test_log_folder_path.exists():
        shutil.rmtree(test_log_folder_path, ignore_errors=True)
    test_log_folder_path.mkdir(parents=True)
    return str(test_log_folder_path)


@pytest.fixture
def force_download(request: pytest.FixtureRequest) -> bool:
    """
    Force artifacts download
    """
    value = request.config.getoption("force_download")
    logging.debug("Force download: %s", value)
    return value


REGISTER_PARAM_ALL_ITEMS: str = "all"


def _parse_parameters(
    params: Iterable[str],
) -> Tuple[Tuple[str, Optional[str], str, str], ...]:
    client_parameters = []
    for item in params:
        if item.strip():
            try:
                param_long_name, value = item.split("=")
                kind, name, key = param_long_name.split(".", 2)
                client_parameters.append(
                    (
                        kind,
                        name if name.strip().lower() != REGISTER_PARAM_ALL_ITEMS else None,
                        key,
                        yaml.load(value, yaml.FullLoader),
                    )
                )
            except ValueError:
                raise ValueError(
                    f"Invalid parameter syntax '{item}'. "
                    "Please use: type.name.key=value "
                    "where type can be 'ue', 'gnb' or '5gc' and name can be 'all'"
                ) from None
    return tuple(client_parameters)


@pytest.fixture
def register_parameter(
    request: pytest.FixtureRequest,
) -> Tuple[Tuple[str, Optional[str], str, str], ...]:
    """
    Agent parameters
    """
    client_parameters = _parse_parameters(request.config.getoption("register_parameter"))
    logging.debug("Register parameters: %s", client_parameters)
    return client_parameters


@pytest.fixture
def register_template(
    request: pytest.FixtureRequest,
) -> Tuple[Tuple[str, Optional[str], str, str], ...]:
    """
    Agent templates
    """
    client_templates = _parse_parameters(request.config.getoption("register_template"))
    logging.debug("Register templates: %s", client_templates)
    return tuple(client_templates)


def _add_cmd_and_ini(parser: pytest.Parser, name: str, **kwargs):
    default = kwargs.pop("default", None)
    parser.addoption("--" + name.replace("_", "-"), **kwargs)
    parser.addini(name, type="string", default=default, **kwargs)


def _get_cmd_and_ini(config: pytest.Config, name: str) -> str:
    value = config.getini(name)
    value_cmd = config.getoption(name)
    if value_cmd is not None:
        value = value_cmd
    return value
