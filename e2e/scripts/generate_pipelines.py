#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Generates dynamically the pipelines declared in PIPELINES, whose stages and jobs are given by
the test suites folder structure
"""

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

import yaml

# Pipelines to generate and the variables added to every one of their jobs. MARKERS is the
# pytest marker expression selecting the test cases the pipeline runs, usually the testbed
# group every test case of a testbed is marked with. A pipeline only gets a job for the test
# suite files holding at least one test case it selects.
PIPELINES: Dict[str, Dict[str, object]] = {
    "functional": {"MARKERS": "zmq or test_mode_ue"},
    "interop": {"MARKERS": "interop"},
    "performance": {"MARKERS": "s72 or test_mode_ru"},
    "rf": {"MARKERS": "rf or android"},
}

# Base file holding the builds and the `.<pipeline>_e2e` job of a pipeline, for the pipelines not
# using their own `<name>_base.yml`. Pipelines sharing a testbed also share their builds, so they
# share the file declaring them.
PIPELINE_BASES: Dict[str, str] = {
    "functional": "zmq",
    "interop": "zmq",
    "performance": "rt",
}

# Retina request a test case with no explicit one falls back to, and the testbed groups the
# requests are marked with. Both mirror the test loader, which is what actually marks the test
# cases: see RetinaTestDefinition.from_dict and RETINA_REQUEST_GROUPS in
# e2e/tests/steps/test_loader.py.
DEFAULT_RETINA_REQUEST = "zmq_mme"
RETINA_REQUEST_GROUPS = ("android", "interop", "rf", "s72", "test_mode", "viavi", "zmq")

# Identifiers of a pytest marker expression, that is everything but its boolean operators.
MARKER_EXPRESSION_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*")
MARKER_EXPRESSION_OPERATORS = {"and", "not", "or"}

# Extensions the test loader picks test suite files up by.
SUITE_EXTENSIONS = (".yml", ".yaml")


def generate_header():
    """
    Generates the licensing header file and returns it.
    """

    header = """# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
    return header


def generate_spec():
    """
    Generates the spec section for the pipeline yml file and returns it.
    """

    spec = """spec:
  inputs:
    ocudu_path:
      type: string
      default: ocudu/ocudu
      description: "OCUDU repository path."
    ocudu_ref:
      type: string
      default: dev
      description: "OCUDU reference branch or tag."
---
"""
    return spec


@dataclass
class Job:
    """
    Job class definition.
    """

    name: str
    stage: str
    pipeline_name: str
    variables: Dict[str, object]

    def format(self):
        """
        Formats the job into an string and returns it.
        """

        formatted = f"""{self.name}:
  stage: {self.stage}
  extends: .{self.pipeline_name}_e2e
  rules:
    - if: $CI_PIPELINE_SCHEDULE_DESCRIPTION =~ /^{self.pipeline_name}/
    - when: manual
      allow_failure: true
  variables:
    KEYWORDS: "{self.stage}.{self.name}."
    TESTBED: dynamic
"""

        # Pipeline variables, dumped as json so that any scalar type is valid yaml.
        for key, value in self.variables.items():
            formatted += f"    {key}: {json.dumps(value)}\n"

        return formatted


class Pipeline:
    """
    Pipeline class definition.
    """

    def __init__(self, name, variables=None):
        """
        Initializes the members of the Pipeline class. The pipeline name is used for its job
        names, its generated file name, its schedule description and the `<name>_base.yml`
        file providing the `.<name>_e2e` job its jobs extend.
        """

        self.name = name
        self.base = PIPELINE_BASES.get(name, name)
        self.variables = variables if variables is not None else {}
        self.markers = get_expression_markers(self.variables.get("MARKERS"))
        self.stages = []
        self.jobs = []

    def runs_suite(self, suite_markers):
        """
        Tells whether this pipeline selects any test case of a test suite tagged with the
        given markers. A pipeline selecting no marker in particular runs every test suite.
        """

        return not self.markers or bool(self.markers & suite_markers)

    def append_stage(self, stage):
        """
        Appends the given stage to the pipeline.
        """

        self.stages.append(stage)

    def append_job(self, job):
        """
        Appends the given job to the pipeline.
        """

        self.jobs.append(job)

    def get_name(self):
        """
        Gets the pipeline name.
        """

        return self.name

    def get_base(self):
        """
        Gets the name of the base file the pipeline takes its builds and `_e2e` job from.
        """

        return self.base

    def get_variables(self):
        """
        Gets the pipeline variables, added to every one of its jobs.
        """

        return self.variables

    def get_stages(self):
        """
        Gets the pipeline stages
        """

        return self.stages

    def format(self):
        """
        Formats the pipeline into an string and returns it.
        """

        formatted = ""

        for job in self.jobs:
            formatted += job.format() + "\n"

        # Remove last \n from the formatted text
        formatted = formatted[:-1]

        return formatted


def get_expression_markers(expression) -> Set[str]:
    """
    Gets the marker names used in the given pytest marker expression. Its boolean operators
    are not interpreted, so for anything but a plain `a or b` expression the result is a
    superset of the markers the expression selects.
    """

    return {
        marker
        for marker in MARKER_EXPRESSION_IDENTIFIER.findall(expression or "")
        if marker not in MARKER_EXPRESSION_OPERATORS
    }


def get_request_group(retina_request: str) -> str:
    """
    Gets the testbed group of the given retina request, or the request itself if it is not
    part of any of the known groups, as the test loader does.
    """

    for group in RETINA_REQUEST_GROUPS:
        if retina_request == group or retina_request.startswith(f"{group}_"):
            return group

    return retina_request


def get_suite_markers(path) -> Set[str]:
    """
    Gets the testbed markers the test cases of the given test suite file are tagged with by the
    test loader: the retina request of every test case and its group. The feature ids it also
    marks them with are of no use to tell the pipelines apart.
    """

    try:
        with open(path, encoding="utf-8") as f:
            suite = yaml.safe_load(f) or {}
    except (IOError, yaml.YAMLError) as e:
        print(f"⚠️ Error reading {path}: {e}")
        return set()

    markers: Set[str] = set()

    for test_case in suite.values():
        # Entries holding nothing but anchors to be reused are not test cases.
        if not isinstance(test_case, dict) or "template" not in test_case:
            continue
        retina_request = test_case.get("request", DEFAULT_RETINA_REQUEST)
        markers.update((retina_request, get_request_group(retina_request)))

    return markers


def iterate_ordered_hierarchy(path, pipelines, level=0):
    """
    Iterates over the given path at the given level and fills the given pipelines, all of
    them fed from the same hierarchy: the first level holds the stages and the second one
    the test suite files, one job each.
    """

    path = Path(path)

    # Stages are folders, so anything else at that level is not one.
    if level == 1 and not path.is_dir():
        return

    # If we are on level two it means we are on the jobs level.
    if level == 2:
        if path.suffix not in SUITE_EXTENSIONS:
            return

        name = path.stem  # Call stem to remove the file extension from the name
        stage = path.parents[0].name

        # A pipeline selecting none of the test cases of a suite gets no job for it: it would
        # run pytest with a filter matching nothing, which pytest reports as an error.
        suite_markers = get_suite_markers(path)
        selected = [pipeline for pipeline in pipelines if pipeline.runs_suite(suite_markers)]

        if not selected:
            print(f"🟡 No pipeline runs {path}: none of them selects any of its markers")

        for pipeline in selected:
            if stage not in pipeline.get_stages():
                pipeline.append_stage(stage)
            pipeline.append_job(Job(name, stage, pipeline.get_name(), pipeline.get_variables()))

        return

    # There are no more defined levels.
    if level > 2:
        return

    # Iterate over the following level
    if path.is_dir():
        for child in sorted(path.iterdir()):
            iterate_ordered_hierarchy(child, pipelines, level + 1)


def create_pipeline_file(path, pipeline):
    """
    Creates the yml describing the given pipeline at the given path.
    """

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(generate_header())
            f.write(pipeline.format())
            print(f"🟢 Successfully created {path}")
    except IOError as e:
        print(f"⚠️ Error writing to file: {e}")


def generate_stages_file(stages_output_path, dynamic_stages):
    """
    Generates .gitlab-ci-stages.yml at the repo root with the full stages list.
    """

    path = Path(stages_output_path) / ".gitlab-ci-stages.yml"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(generate_header())
            stages = [
                "ci",
                "static",
                "build",
                "e2e",
                "viavi",
            ]
            stages.extend(dynamic_stages)
            stages = list(dict.fromkeys(stages))
            f.write("stages:\n")
            for stage in stages:
                f.write(f"  - {stage}\n")
            print(f"🟢 Successfully created {path}")
    except IOError as e:
        print(f"⚠️ Error writing to file: {e}")


def generate_e2e_template(stages_output_path, pipelines_output_path, pipeline_includes):
    """
    Generates e2e/ci/e2e_template.yml with spec inputs, per-pipeline base and
    conditional config includes, and MR child pipeline trigger jobs.
    """

    # Path prefix for e2e/ci relative to repo root (used in local: entries)
    ci_rel = os.path.relpath(pipelines_output_path, start=stages_output_path)

    path = Path(pipelines_output_path) / "e2e_template.yml"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(generate_header())
            f.write(generate_spec())
            # Per-pipeline: unconditional base + conditional config
            f.write("include:\n")
            written_bases = set()
            for pipeline, include_path in pipeline_includes:
                # Pipelines sharing a base file must not include it twice
                if pipeline.get_base() not in written_bases:
                    written_bases.add(pipeline.get_base())
                    f.write(f"  - local: {ci_rel}/{pipeline.get_base()}_base.yml\n")
                f.write(f"  - local: {include_path}\n")
                f.write("    rules:\n")
                f.write(f"      - if: $CI_PIPELINE_SCHEDULE_DESCRIPTION =~ /^{pipeline.get_name()}/\n")
            f.write("\n")
            # MR child pipeline trigger jobs + promotion jobs, one pair per discovered pipeline
            for i, (pipeline, include_path) in enumerate(pipeline_includes):
                name = pipeline.get_name()
                if i > 0:
                    f.write("\n")
                f.write(f"{name}:\n")
                f.write("  extends: .trigger e2e\n")
                f.write("  trigger:\n")
                f.write("    include:\n")
                f.write(f"      - local: {ci_rel}/child_template.yml\n")
                f.write("        inputs:\n")
                f.write("          ocudu_path: $[[ inputs.ocudu_path ]]\n")
                f.write("          ocudu_ref: $[[ inputs.ocudu_ref ]]\n")
                f.write(f"      - local: {ci_rel}/{pipeline.get_base()}_base.yml\n")
                f.write(f"      - local: {include_path}\n")
                f.write("    strategy: mirror\n")
                f.write("    forward:\n")
                f.write("      pipeline_variables: true\n")
                f.write("\n")
                f.write(f"{name} promotion:\n")
                f.write("  extends: .ocudu promotion\n")
                f.write("  rules:\n")
                f.write(f"    - if: $CI_PIPELINE_SCHEDULE_DESCRIPTION =~ /^{name}/\n")
                f.write("  variables:\n")
                f.write(f"    BRANCH: srs_{name}\n")
            print(f"🟢 Successfully created {path}")
    except IOError as e:
        print(f"⚠️ Error writing to file: {e}")


def generate_pipelines_dynamically(input_path, pipelines_output_path, stages_output_path):
    """
    Generates the needed pipelines dynamically.
    """

    # Every pipeline runs the same hierarchy of test suite files.
    pipelines: List[Pipeline] = [Pipeline(name, variables) for name, variables in PIPELINES.items()]

    iterate_ordered_hierarchy(input_path, pipelines)

    dynamic_stages = []
    pipeline_includes = []

    base = Path(pipelines_output_path)
    base.mkdir(parents=True, exist_ok=True)

    for pipeline in pipelines:
        pipeline_path = base / f"{pipeline.get_name()}_config.yml"
        create_pipeline_file(pipeline_path, pipeline)

        dynamic_stages.extend(pipeline.get_stages())

        # Include path relative to the generated file, for the conditional include block.
        include_path = os.path.relpath(pipeline_path, start=stages_output_path)
        pipeline_includes.append((pipeline, include_path))

    generate_stages_file(stages_output_path, dynamic_stages)
    generate_e2e_template(stages_output_path, pipelines_output_path, pipeline_includes)


def main():
    """
    Entrypoint
    """

    parser = argparse.ArgumentParser(
        description="Generates dynamically the pipelines given by the project folder structure"
    )

    parser.add_argument(
        "--input_path",
        type=str,
        help="Path where the folder structure representing the pipeline is. (default: `%(default)s`)'",
        default="../tests/suites",
    )

    parser.add_argument(
        "--pipelines_output_path",
        type=str,
        help="Output path where the yml files that describe the pipelines "
        "will be generated. (default: `%(default)s`)'",
        default="../ci",
    )

    parser.add_argument(
        "--stages_output_path",
        type=str,
        help="Output path where the yml file that holds the stages will be generated. (default: `%(default)s`)'",
        default="../../",
    )

    args = parser.parse_args()

    generate_pipelines_dynamically(args.input_path, args.pipelines_output_path, args.stages_output_path)


if __name__ == "__main__":
    main()
