#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Fixtures related with artifacts and report
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import grpc
import pytest
from pytest_html import extras
from retina.client.exception import clean_grpc_traceback, ErrorReportedByAgent

from retina.launcher.cmd_args import get_folder_name
from retina.launcher.reporter import REPORT_FILENAME

TEST_SUCCESS_FIELD: str = "_success_by_retina_plugin"


@pytest.hookimpl(trylast=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):  # pylint: disable=unused-argument
    """
    Adds a "success" field to the node and handles extra URL information.
    """
    # Exchange grpc exception for a custom one
    if call.excinfo is not None and isinstance(call.excinfo.value, grpc.RpcError):
        # pylint: disable=protected-access
        # Remove pure grpc entries in the traceback
        clean_grpc_traceback(call.excinfo._excinfo[2])
        # Set custom execinfo
        call.excinfo._excinfo = (
            ErrorReportedByAgent,
            ErrorReportedByAgent(call.excinfo.value),
            call.excinfo._excinfo[2],
        )
    outcome = yield
    report: pytest.TestReport = outcome.get_result()

    # Set status param
    prev_status = getattr(item, TEST_SUCCESS_FIELD, True)
    setattr(item, TEST_SUCCESS_FIELD, prev_status and not report.failed)

    # Add extra URL information to the report
    if report.when == "call":
        href = "./" + str(
            Path(get_folder_name(item.config, item.nodeid))
            .resolve()
            .joinpath(REPORT_FILENAME)
            .relative_to(Path(item.config.getoption("htmlpath")).resolve().parent)
        )
        report.extras = getattr(report, "extras", [])
        report.extras.append(extras.url(href, name="🔗 Go to logs and configs"))


def pytest_html_report_title(report) -> None:
    """
    Default html report title
    """
    report.title = "Retina Tests"


@dataclass
class RetinaTestData:
    """
    Set of variables that can be modified by the test
    """

    download_artifacts: bool
    test_config: Dict
