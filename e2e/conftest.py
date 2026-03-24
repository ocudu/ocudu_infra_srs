# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Pytest configuration
"""

import os
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pytest
from _pytest.python import Module as _BaseModule
from pytest_metadata.plugin import metadata_key


def pytest_configure(config):
    """
    Add custom variables to the report
    """
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


class Suite(pytest.Collector):  # pylint: disable=too-few-public-methods
    """Virtual group node that creates hierarchy levels in the collection tree."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._suite_children: list = []

    def collect(self):
        """Collect children (items and collectors) for this collector."""
        return self._suite_children


class Module(_BaseModule):  # pylint: disable=too-few-public-methods
    """Module that builds a Suite hierarchy from :: separators in test_definition names."""

    def collect(self):
        """Collect children (items and collectors) for this collector."""
        group_cache: dict = {}
        top_level_suites: list = []

        for item in super().collect():
            if not (hasattr(item, "callspec") and "test_definition" in item.callspec.params):
                yield item
                continue

            parts = item.callspec.params["test_definition"].name.split("::")

            if len(parts) <= 1:
                yield item
                continue

            current_parent = self
            for i, group_name in enumerate(parts[:-1]):
                cache_key = tuple(parts[: i + 1])
                if cache_key not in group_cache:
                    suite = Suite.from_parent(current_parent, name=group_name)
                    if i == 0:
                        top_level_suites.append(suite)
                    else:
                        group_cache[tuple(parts[:i])]._suite_children.append(suite)  # pylint: disable=protected-access
                    group_cache[cache_key] = suite
                current_parent = group_cache[cache_key]

            leaf_name = parts[-1]
            item.name = leaf_name
            item.parent = current_parent
            item._nodeid = f"{current_parent.nodeid}::{leaf_name}"  # pylint: disable=protected-access
            group_cache[tuple(parts[:-1])]._suite_children.append(item)  # pylint: disable=protected-access

        yield from top_level_suites


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


def pytest_pycollect_makemodule(module_path: Path, parent: Any):
    """
    Return a Module collector or None for the given path.
    This hook will be called for each matching test module path.
    """
    return Module.from_parent(parent, path=module_path)


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
