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
    Add custom variables to the report, and rewrite bare YAML paths (no .yml
    extension) in config.args so pytest can resolve them.
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

    if not hasattr(config, "args"):
        return
    suites_dir = Path(__file__).parent / "tests" / "suites"
    conftest_dir = Path(__file__).parent
    for i, arg in enumerate(config.args):
        if arg.startswith("-"):
            continue
        path_part, sep, rest = arg.partition("::")
        orig = Path(path_part)
        resolved = orig if orig.is_absolute() else conftest_dir / orig
        if not resolved.exists():
            resolved_yml = resolved.with_suffix(".yml")
            if resolved_yml.exists():
                try:
                    resolved_yml.relative_to(suites_dir)
                    config.args[i] = str(orig.with_suffix(".yml")) + (f"::{rest}" if sep else "")
                except ValueError:
                    pass


class YamlFileCollector(pytest.Collector):  # pylint: disable=too-few-public-methods
    """
    Collects tests defined in a single YAML file under tests/suites/.

    e.g. 'pytest tests/suites/functional/multiue/ping.yml' finds all tests
    whose test_definition.name starts with 'functional/multiue/ping::' and
    yields them with nodeids like tests/suites/functional/multiue/ping::baseline.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._yaml_path: Any = None

    def _module_parent(self) -> Any:
        """Walk parent chain to find Dir(tests/suites)."""
        suites_dir = Path(__file__).parent / "tests" / "suites"
        node = self.parent
        while node is not None:
            if getattr(node, "path", None) is not None and Path(str(node.path)) == suites_dir:
                return node
            node = node.parent
        return self.parent

    def collect(self):
        """Yield Function items whose test_definition belongs to this YAML file."""
        if self._yaml_path is None:
            return
        suites_dir = Path(__file__).parent / "tests" / "suites"
        tests_dir = Path(__file__).parent / "tests"
        rel_prefix = str(Path(self._yaml_path).relative_to(suites_dir).with_suffix("")) + "::"
        module_parent = self._module_parent()
        for py_file in sorted(tests_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module = _BaseModule.from_parent(module_parent, path=py_file)
            for item in _BaseModule.collect(module):
                if not (hasattr(item, "callspec") and "test_definition" in item.callspec.params):
                    continue
                if not item.callspec.params["test_definition"].name.startswith(rel_prefix):
                    continue
                test_name = item.callspec.params["test_definition"].name.rsplit("::", 1)[-1]
                orig_module = item.module  # capture before re-parenting
                item.name = test_name
                item.parent = self
                item._nodeid = f"{self.nodeid}::{test_name}"  # pylint: disable=protected-access
                # Preserve item.module so plugins (e.g. pytest-random-order) can
                # still access it after the parent chain no longer contains a Module.
                item.__class__ = type(  # pylint: disable=invalid-class-object
                    item.__class__.__name__,
                    (item.__class__,),
                    {"module": property(lambda s, m=orig_module: m)},  # type: ignore
                )
                yield item


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
    Collect tests from YAML files under tests/suites/.
    Nodeids omit the .yml extension: tests/suites/functional/multiue/ping::baseline.
    """
    suites_dir = Path(__file__).parent / "tests" / "suites"
    if file_path.suffix not in (".yml", ".yaml"):
        return None
    try:
        file_path.relative_to(suites_dir)
    except ValueError:
        return None
    collector = YamlFileCollector.from_parent(parent, name=file_path.name, path=file_path)
    collector._yaml_path = file_path  # pylint: disable=protected-access
    collector._nodeid = f"{parent.nodeid}/{file_path.name}"  # pylint: disable=protected-access
    return collector


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
