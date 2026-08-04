#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Static checks for E2E test definitions and configuration files.
"""

import ast
import sys
from pathlib import Path
from typing import Any, List

import jinja2
import jinja2.meta
import jinja2.nodes
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

_DEFAULTS_DIR = _E2E_DIR.parent / "retina" / "agent" / "src" / "retina" / "agent" / "parameters"

# Defaults files whose variables are framework-injected (not required in parameters:).
# testbed_defaults is available in all component calls.
_DIR_DEFAULTS_FILES = {
    "gnb": ("testbed_defaults.py", "gnb_defaults.py"),
    "ue": ("testbed_defaults.py", "ue_defaults.py"),
    "core": ("testbed_defaults.py", "fivegc_defaults.py"),
}

# Variables injected by drivers at render time (not in *_defaults.py or parameters:).
# base.py always injects: report_folder, utc_timestamp
_RENDER_INJECTED_VARS = {
    "gnb": {"report_folder", "utc_timestamp", "neighbor_cucp_definition", "fivegc_definition"},
    "ue": {"report_folder", "utc_timestamp", "cell_ru_cfg", "start_time", "subscriber_array"},
    "core": {"report_folder", "utc_timestamp", "subnet_prefix"},
}

# Config file extension required per component directory.
_CONFIG_EXTENSION = {
    "gnb": ".yml",
    "ue": ".cfg",
    "core": ".cfg",
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


def _load_framework_variables(configs_dir_key: str) -> set:
    """Return variable names injected by the Retina framework for a given config dir."""
    names = set()
    for filename in _DIR_DEFAULTS_FILES.get(configs_dir_key, ()):
        path = _DEFAULTS_DIR / filename
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
    return names


def _load_framework_defaults(configs_dir_key: str) -> dict:
    """Return {name: default_value} for scalar-typed parameters in *_defaults.py files."""
    defaults: dict = {}
    for filename in _DIR_DEFAULTS_FILES.get(configs_dir_key, ()):
        path = _DEFAULTS_DIR / filename
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)):
                continue
            val = node.value
            if val is None:
                continue
            if isinstance(val, ast.Constant):
                defaults[node.target.id] = val.value
            elif (
                isinstance(val, ast.UnaryOp)
                and isinstance(val.op, ast.USub)
                and isinstance(val.operand, ast.Constant)
                and isinstance(val.operand.value, (int, float, complex))
            ):
                defaults[node.target.id] = -val.operand.value
    return defaults


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


def _is_set_default_assign(node: Any) -> bool:
    """Return True if *node* is a top-level {% set var = var | default(...) %} assignment."""
    return (
        isinstance(node, jinja2.nodes.Assign)
        and isinstance(node.target, jinja2.nodes.Name)
        and isinstance(node.node, jinja2.nodes.Filter)
        and node.node.name == "default"
        and isinstance(node.node.node, jinja2.nodes.Name)
        and node.node.node.name == node.target.name
    )


def _extract_template_defaults(jinja_ast: Any) -> dict:
    """Return {var_name: default_value} for top-level {% set var = var | default(const) %} nodes.

    Uses as_const() rather than a Const isinstance check: a negative literal such as
    default(-10) parses as Neg(Const(10)), not Const(-10). Nodes that are genuine
    expressions, e.g. default(other_var), raise Impossible and are skipped.
    """
    defaults = {}
    for node in jinja_ast.body:
        if not (_is_set_default_assign(node) and node.node.args):
            continue
        try:
            defaults[node.target.name] = node.node.args[0].as_const()
        except jinja2.nodes.Impossible:
            pass
    return defaults


def _iter_component_items(instance: dict):
    """Yield (component, dir_key, params, configs) for every non-empty item in an instance."""
    for component, dir_key in _COMPONENT_CONFIG_KEY.items():
        node = instance.get(component, {}) or {}
        items = node.get("items") or [node] if "items" in node else [node]
        for item in items:
            item = item or {}
            params = item.get("parameters", {}) or {}
            configs = item.get("config", []) or []
            if params and configs:
                yield component, dir_key, params, configs


def _self_defaulted_vars(jinja_ast: jinja2.nodes.Template) -> set:
    """Return variables declared as  {%- set x = x | default(v) %}.

    find_undeclared_variables misses these: the `set` marks x as declared,
    hiding that x is still read from the render context.
    """
    found: set = set()
    for assign in jinja_ast.find_all(jinja2.nodes.Assign):
        if not isinstance(assign.target, jinja2.nodes.Name):
            continue
        name = assign.target.name
        for f in assign.node.find_all(jinja2.nodes.Filter):
            if f.name == "default" and isinstance(f.node, jinja2.nodes.Name) and f.node.name == name:
                found.add(name)
                break
    return found


def _get_template_vars(dir_key: str, configs: list, env: jinja2.Environment, cache: dict) -> set:
    """Return the union of undeclared Jinja2 variables across *configs*, with caching."""
    result: set = set()
    for filename in configs:
        config_path = _CONFIGS_DIRS[dir_key] / filename
        if not config_path.exists():
            continue
        if config_path not in cache:
            try:
                jinja_ast = env.parse(config_path.read_text())
                cache[config_path] = jinja2.meta.find_undeclared_variables(jinja_ast) | _self_defaulted_vars(jinja_ast)
            except jinja2.TemplateSyntaxError:
                cache[config_path] = set()
        result |= cache[config_path]
    return result


def _safe_add(s: set, v: Any) -> None:
    """Add *v* to *s*, falling back to repr() if *v* is unhashable."""
    try:
        s.add(v)
    except TypeError:
        s.add(repr(v))


def _collect_provided_params() -> dict:
    """Return {config_path: {param_name: set[values]}} of parameters ever supplied by any test."""
    provided: dict = {}
    for _suite_path, suite_data in _load_suite_yamls():
        for _test_key, instance in _iter_test_instances(suite_data):
            for _comp, dir_key, filename, params in _iter_config_refs(instance):
                config_path = _CONFIGS_DIRS[dir_key] / filename
                if config_path.exists():
                    entry = provided.setdefault(config_path, {})
                    for k, v in params.items():
                        _safe_add(entry.setdefault(k, set()), v)
    return provided


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


def check_config_parameter_declarations() -> List[str]:
    """Every non-framework variable in a config must be declared with {% set var = var | default(...) %} at the top."""
    framework_vars_by_dir = {
        dir_key: _load_framework_variables(dir_key) | _RENDER_INJECTED_VARS[dir_key] for dir_key in _CONFIGS_DIRS
    }
    env = jinja2.Environment()
    errors = []

    for dir_key, configs_dir in _CONFIGS_DIRS.items():
        framework_vars = framework_vars_by_dir[dir_key]
        for config_path in sorted(configs_dir.iterdir()):
            if not config_path.is_file():
                continue
            try:
                jinja_ast = env.parse(config_path.read_text())
            except jinja2.TemplateSyntaxError:
                continue  # already caught by check_jinja_syntax

            used_vars = jinja2.meta.find_undeclared_variables(jinja_ast) - framework_vars
            if not used_vars:
                continue

            # Collect {% set var = var | default(...) %} declarations that appear as
            # top-level statements (direct children of the template body, not inside
            # {% if %} / {% for %} blocks).
            top_declared = {node.target.name for node in jinja_ast.body if _is_set_default_assign(node)}
            missing = used_vars - top_declared
            if missing:
                errors.append(
                    f"Config '{dir_key}/{config_path.name}' variables not declared with "
                    f"set+default: {', '.join(sorted(missing))}"
                )

    return errors


def check_dead_parameters() -> List[str]:
    """Parameters defined in a test but consumed by none of its configs.

    A parameter that no referenced config uses is dead — it silently has
    no effect and is likely a typo or leftover from a config change.
    """
    framework_vars = {dir_key: _load_framework_variables(dir_key) for dir_key in _CONFIGS_DIRS}
    consumed_cache: dict = {}  # config_path -> set[str] (all vars, including |default ones)
    dead_params: dict = {}  # (suite_rel, test_key, component) -> set[str]

    env = jinja2.Environment()

    for suite_path, suite_data in _load_suite_yamls():
        suite_rel = suite_path.relative_to(_SUITES_DIR)
        for test_key, instance in _iter_test_instances(suite_data):
            for component, dir_key, params, configs in _iter_component_items(instance):
                consumed = (
                    framework_vars[dir_key]
                    | _RENDER_INJECTED_VARS[dir_key]
                    | _get_template_vars(dir_key, configs, env, consumed_cache)
                )
                dead = set(params.keys()) - consumed
                if dead:
                    dead_params.setdefault((suite_rel, test_key, component), set()).update(dead)

    return [
        f"Suite '{suite_rel}' test '{test_key}' component '{component}' has dead parameters: {', '.join(sorted(ps))}"
        for (suite_rel, test_key, component), ps in sorted(dead_params.items())
    ]


def check_config_extensions() -> List[str]:
    """Config files must use the correct extension for their directory.

    gnb/  → .yml
    ue/   → .cfg
    core/ → .cfg
    """
    errors = []
    for dir_key, configs_dir in _CONFIGS_DIRS.items():
        expected = _CONFIG_EXTENSION[dir_key]
        for config_path in sorted(configs_dir.iterdir()):
            if config_path.is_file() and config_path.suffix != expected:
                errors.append(
                    f"Config '{dir_key}/{config_path.name}' has extension '{config_path.suffix}', expected '{expected}'"
                )
    return errors


def check_never_overridden_parameters() -> List[str]:
    """Config variables declared with set+default but never overridden by any test.

    A variable is "never overridden" when no test passes it at all, or every test that
    does pass it uses the same value as the template default. Both cases are effectively
    constants — simplify by hardcoding the default value and removing the {% set %}.
    """
    provided = _collect_provided_params()
    framework_vars_by_dir = {
        dir_key: _load_framework_variables(dir_key) | _RENDER_INJECTED_VARS[dir_key] for dir_key in _CONFIGS_DIRS
    }
    env = jinja2.Environment()
    warnings = []

    for dir_key, configs_dir in _CONFIGS_DIRS.items():
        framework_vars = framework_vars_by_dir[dir_key]
        for config_path in sorted(configs_dir.iterdir()):
            if not config_path.is_file():
                continue
            try:
                jinja_ast = env.parse(config_path.read_text())
            except jinja2.TemplateSyntaxError:
                continue
            top_declared = {
                node.target.name
                for node in jinja_ast.body
                if _is_set_default_assign(node) and node.target.name not in framework_vars
            }
            if not top_declared:
                continue
            template_defaults = _extract_template_defaults(jinja_ast)
            config_provided = provided.get(config_path, {})
            never_overridden = {
                var
                for var in top_declared
                if var not in config_provided
                or (var in template_defaults and all(v == template_defaults[var] for v in config_provided[var]))
            }
            if never_overridden:
                warnings.append(
                    f"Config '{dir_key}/{config_path.name}' variables never overridden by any test "
                    f"(consider hardcoding): {', '.join(sorted(never_overridden))}"
                )

    return warnings


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


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_ALL_CHECKS = [
    check_schema_validity,
    check_referenced_configs_exist,
    check_all_configs_referenced,
    check_jinja_syntax,
    check_config_parameter_declarations,
    check_never_overridden_parameters,
    check_dead_parameters,
    check_config_extensions,
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
