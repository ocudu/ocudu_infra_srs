# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Pytest configuration
"""

import logging
import os
from collections import OrderedDict

import pytest
from pytest_metadata.plugin import metadata_key


def pytest_configure(config):
    """
    Add custom variables to the report
    """

    logging.getLogger("kubernetes").setLevel(logging.INFO)

    md = config.stash[metadata_key]
    md.clear()
    md.update(
        OrderedDict(
            {
                "OCUDU_COMMIT": os.getenv("OCUDU_COMMIT", "N/A"),
                "CI_COMMIT_SHA": os.getenv("CI_COMMIT_SHA", "N/A"),
                "CI_JOB_NAME": os.getenv("CI_JOB_NAME", "N/A"),
                "CI_JOB_ID": os.getenv("CI_JOB_ID", "N/A"),
                "CI_PIPELINE_ID": os.getenv("CI_PIPELINE_ID", "N/A"),
            }
        )
    )

    if job_name := os.getenv("CI_JOB_NAME", ""):
        config._inicache["junit_suite_name"] = job_name  # pylint: disable=protected-access


@pytest.fixture(autouse=True, scope="session")
def _junit_suite_properties(record_testsuite_property):
    record_testsuite_property("ocudu_commit", os.getenv("OCUDU_COMMIT", ""))
    record_testsuite_property("test_commit", os.getenv("CI_COMMIT_SHA", ""))
    record_testsuite_property("url", os.getenv("CI_JOB_URL", ""))


def pytest_collection_modifyitems(items):
    """
    Record all markers as JUnit XML properties.
    """
    for item in items:
        markers = []
        for marker in item.iter_markers():
            if marker.name in ("parametrize", "skip", "skipif", "xfail", "usefixtures", "filterwarnings"):
                continue
            markers.append(marker.name)
        item.user_properties.append(("markers", ";".join(markers)))


def pytest_addoption(parser: pytest.Parser):
    """
    Add Viavi options to pytest
    """
    parser.addoption(
        "--viavi-manual-campaign-filename", action="store", default="default_filename", help="Viavi campaign filename"
    )
    parser.addoption("--viavi-manual-test-name", action="store", default="default_test", help="Viavi test name")
    parser.addoption("--viavi-manual-test-timeout", action="store", type=int, default=1800, help="Viavi test timeout")
    parser.addoption("--viavi-manual-gnb-arguments", action="store", type=str, default="", help="Viavi gnb arguments")
