#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Static checks for E2E test definitions and configuration files.
"""

import ast
import sys
from pathlib import Path
from typing import List

import jinja2
import jsonschema
import yaml

# ---------------------------------------------------------------------------
# Paths (relative to this script's location: e2e/scripts/)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent
_E2E_DIR = _SCRIPTS_DIR.parent
_TESTS_DIR = _E2E_DIR / "tests"
_SUITES_DIR = _TESTS_DIR / "suites"
_CRITERIAS_DIR = _TESTS_DIR / "criterias"
_REQUESTS_DIR = _E2E_DIR / "retina_requests"

_CONFIGS_DIRS = {
    "gnb": _TESTS_DIR / "configs" / "gnb",
    "ue": _TESTS_DIR / "configs" / "ue",
    "core": _TESTS_DIR / "configs" / "core",
}


# Dynamically-generated criteria modules and which source modules they alias.
# These files contain no static ClassDef nodes — their valid class names are
# the union of the source modules listed here.
_DYNAMIC_CRITERIA_MODULES: dict = {
    "gnb": ("du", "cu_cp", "cu_up"),
    "cu": ("cu_cp", "cu_up"),
}

# Config keys in a test definition that map to a component configs dir.
_COMPONENT_CONFIG_KEY = {
    "gnb": "gnb",
    "du": "gnb",
    "cu": "gnb",
    "cu_cp": "gnb",
    "cu_up": "gnb",
    "ue": "ue",
    "core": "core",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_suite_yamls() -> List[tuple]:
    """Return [(path, parsed_dict), ...] for all suite YAML files."""
    results = []
    for path in sorted(_SUITES_DIR.rglob("*.yml")):
        with path.open() as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            results.append((path, data))
    return results


def _iter_test_instances(suite_data: dict):
    """Yield (key, instance) for each test-instance dict in a parsed suite YAML."""
    for key, value in suite_data.items():
        if isinstance(value, dict):
            yield key, value


def _iter_config_refs(instance: dict):
    """Yield (component, configs_dir_key, filename, parameters) for every config reference.

    A component node is either flat ({config: [...], parameters: {...}})
    or multi-instance ({items: [{config: [...], parameters: {...}}, ...]}).
    """
    for component, configs_dir_key in _COMPONENT_CONFIG_KEY.items():
        node = instance.get(component, {}) or {}
        if "items" in node:
            for item in node["items"] or []:
                item = item or {}
                params = item.get("parameters", {}) or {}
                for filename in item.get("config", []):
                    yield component, configs_dir_key, filename, params
        else:
            params = node.get("parameters", {}) or {}
            for filename in node.get("config", []):
                yield component, configs_dir_key, filename, params


def _iter_criteria_entries(instance: dict):
    """Yield (module_name, class_name, value) for each criteria entry in a test instance."""
    criteria = instance.get("criteria", {}) or {}
    for key, value in criteria.items():
        if "." in key:
            module_name, class_name = key.split(".", 1)
            yield module_name, class_name, value


def _load_criteria_classes() -> dict:
    """Return {module_name: set[class_name]} for all criteria modules.

    Dynamically-generated modules (gnb, cu) have no static ClassDef nodes;
    their valid class names are computed as the union of their source modules.
    """
    static_classes: dict = {}
    for path in sorted(_CRITERIAS_DIR.glob("*.py")):
        name = path.stem
        if name in ("__init__", *_DYNAMIC_CRITERIA_MODULES):
            continue
        tree = ast.parse(path.read_text())
        static_classes[name] = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}

    result = dict(static_classes)
    for mod, sources in _DYNAMIC_CRITERIA_MODULES.items():
        result[mod] = set().union(*(static_classes.get(s, set()) for s in sources))
    return result


def _find_load_tests_functions(module_path: Path) -> set:
    """Return function names decorated with @load_tests in a Python source file."""
    tree = ast.parse(module_path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Name) and dec.id == "load_tests") or (
                    isinstance(dec, ast.Attribute) and dec.attr == "load_tests"
                ):
                    names.add(node.name)
    return names


# JSON Schema for a single test instance (one key inside a suite YAML).
_TEST_DEFINITION_SCHEMA: dict = {
    "$defs": {
        "item_config": {
            "type": "object",
            "properties": {
                "config": {"type": "array", "items": {"type": "string"}},
                "parameters": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "node_type_definition": {
            "type": "object",
            "properties": {
                "config": {"type": "array", "items": {"type": "string"}},
                "parameters": {"type": "object"},
                "items": {"type": "array", "items": {"$ref": "#/$defs/item_config"}},
            },
            "additionalProperties": False,
        },
    },
    "type": "object",
    "properties": {
        "template": {"type": "string"},
        "request": {"type": "string"},
        "feature_ids": {"type": "array", "items": {"type": "string"}},
        "criteria": {"type": "object", "additionalProperties": {}},
        "ue": {"$ref": "#/$defs/node_type_definition"},
        "cu": {"$ref": "#/$defs/node_type_definition"},
        "cu_cp": {"$ref": "#/$defs/node_type_definition"},
        "cu_up": {"$ref": "#/$defs/node_type_definition"},
        "du": {"$ref": "#/$defs/node_type_definition"},
        "gnb": {"$ref": "#/$defs/node_type_definition"},
        "core": {"$ref": "#/$defs/node_type_definition"},
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# Checks — each returns a list of error strings (empty = no errors)
# ---------------------------------------------------------------------------


def check_schema_validity() -> List[str]:
    """Every test instance must conform to the test definition schema."""
    errors = []
    for suite_path, suite_data in _load_suite_yamls():
        for test_key, instance in _iter_test_instances(suite_data):
            try:
                jsonschema.validate(instance, _TEST_DEFINITION_SCHEMA)
            except jsonschema.ValidationError as e:
                errors.append(f"{suite_path}: test '{test_key}' schema error: {e.message}")
    return errors


def check_referenced_configs_exist() -> List[str]:
    """All config filenames referenced in tests must exist."""
    errors = []
    for suite_path, suite_data in _load_suite_yamls():
        for _key, instance in _iter_test_instances(suite_data):
            for _comp, dir_key, filename, _params in _iter_config_refs(instance):
                config_path = _CONFIGS_DIRS[dir_key] / filename
                if not config_path.exists():
                    errors.append(f"{suite_path}: references missing config '{dir_key}/{filename}'")
    return errors


def check_all_configs_referenced() -> List[str]:
    """Every config file must be referenced by at least one test."""
    referenced: dict = {dir_key: set() for dir_key in _CONFIGS_DIRS}
    for _suite_path, suite_data in _load_suite_yamls():
        for _key, instance in _iter_test_instances(suite_data):
            for _comp, dir_key, filename, _params in _iter_config_refs(instance):
                referenced[dir_key].add(filename)

    errors = []
    for dir_key, configs_dir in _CONFIGS_DIRS.items():
        for config_path in sorted(configs_dir.iterdir()):
            if config_path.is_file() and config_path.name not in referenced[dir_key]:
                errors.append(f"Config '{dir_key}/{config_path.name}' not referenced in any test")
    return errors


def check_jinja_syntax() -> List[str]:
    """All config files must be syntactically valid Jinja2 templates."""
    env = jinja2.Environment()
    errors = []
    for configs_dir in _CONFIGS_DIRS.values():
        for config_path in sorted(configs_dir.iterdir()):
            if not config_path.is_file():
                continue
            try:
                env.parse(config_path.read_text())
            except jinja2.TemplateSyntaxError as e:
                errors.append(f"{config_path}: Jinja2 syntax error at line {e.lineno}: {e.message}")
    return errors


def check_criteria_classes_exist() -> List[str]:
    """Criteria keys in tests must map to existing Python classes.

    'du.dl_bitrate_gt' must resolve to class 'dl_bitrate_gt' in
    criterias/du.py. Typos currently only fail at runtime.
    """
    criteria_classes = _load_criteria_classes()
    errors = []
    for suite_path, suite_data in _load_suite_yamls():
        for test_key, instance in _iter_test_instances(suite_data):
            for module_name, class_name, _ in _iter_criteria_entries(instance):
                if module_name not in criteria_classes:
                    errors.append(f"{suite_path}: test '{test_key}' references unknown criteria module '{module_name}'")
                elif class_name not in criteria_classes[module_name]:
                    errors.append(
                        f"{suite_path}: test '{test_key}' references unknown criteria '{module_name}.{class_name}'"
                    )
    return errors


def check_orphan_criteria() -> List[str]:
    """Criteria classes defined in criterias/*.py but never used in any test."""
    used: set = set()
    for _, suite_data in _load_suite_yamls():
        for _, instance in _iter_test_instances(suite_data):
            for module_name, class_name, _ in _iter_criteria_entries(instance):
                used.add((module_name, class_name))

    criteria_classes = _load_criteria_classes()
    errors = []
    for module_name, class_names in sorted(criteria_classes.items()):
        if module_name in _DYNAMIC_CRITERIA_MODULES:
            continue  # aliases only; no original definitions to check
        for class_name in sorted(class_names):
            if class_name in ("errors_le", "warnings_le"):
                continue  # generated by default; absence in tests is expected
            # viavi criteria should be migrated to use the same mechanism as other modules
            if module_name == "viavi":
                continue
            if (module_name, class_name) not in used:
                errors.append(f"Criteria '{module_name}.{class_name}' is defined but never used in any test")
    return errors


def check_template_validity() -> List[str]:
    """'template:' values must map to a @load_tests-decorated function.

    'ue_simulator.test_gnb' is valid iff tests/ue_simulator.py has a
    function 'test_gnb' decorated with @load_tests.
    """
    cache: dict = {}  # module_name -> set[str] | None (None = module file missing)
    errors = []
    for suite_path, suite_data in _load_suite_yamls():
        for test_key, instance in _iter_test_instances(suite_data):
            template = instance.get("template")
            if not template or "." not in template:
                continue
            module_name, func_name = template.split(".", 1)
            if module_name not in cache:
                module_path = _TESTS_DIR / f"{module_name}.py"
                cache[module_name] = _find_load_tests_functions(module_path) if module_path.exists() else None
            if cache[module_name] is None:
                errors.append(
                    f"{suite_path}: test '{test_key}' template '{template}' references missing '{module_name}'"
                )
            elif func_name not in cache[module_name]:
                errors.append(
                    f"{suite_path}: test '{test_key}' template '{template}'"
                    f" has no @load_tests-decorated function '{func_name}'"
                )
    return errors


def check_request_validity() -> List[str]:
    """'request:' values must map to an existing file in retina_requests/."""
    errors = []
    for suite_path, suite_data in _load_suite_yamls():
        for test_key, instance in _iter_test_instances(suite_data):
            request = instance.get("request")
            if request and not (_REQUESTS_DIR / f"{request}.yml").exists():
                errors.append(f"{suite_path}: test '{test_key}' references missing request '{request}.yml'")
    return errors


_ALL_CHECKS = [
    check_schema_validity,
    check_referenced_configs_exist,
    check_all_configs_referenced,
    check_jinja_syntax,
    check_criteria_classes_exist,
    check_orphan_criteria,
    check_template_validity,
    check_request_validity,
]


def _main() -> int:
    all_errors = []
    for check in _ALL_CHECKS:
        errors = check()
        if errors:
            print(f"[FAIL] {check.__name__}")
            for error in errors:
                print(f"  {error}")
        else:
            print(f"[ OK ] {check.__name__}")
        all_errors.extend(errors)

    if all_errors:
        print(f"\n{len(all_errors)} error(s) found.")
        return 1

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
