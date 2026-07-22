#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Generates dynamically the pipelines given by the project folder structure
"""

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


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

    def format(self):
        """
        Formats the job into an string and returns it.
        """

        return f"""{self.name}:
  stage: {self.stage}
  extends: .{self.pipeline_name}_e2e
  rules:
    - if: $CI_PIPELINE_SCHEDULE_DESCRIPTION =~ /{self.pipeline_name}/
    - when: manual
      allow_failure: true
  variables:
    KEYWORDS: "{self.pipeline_name}.{self.stage}.{self.name}."
    TESTBED: dynamic
"""


class Pipeline:
    """
    Pipeline class definition.
    """

    def __init__(self, name):
        """
        Initializes the members of the Pipeline class.
        """

        self.name = name
        self.stages = []
        self.jobs = []

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


def iterate_ordered_hierarchy(path, pipelines, level=0):
    """
    Iterates over the given path at the given level and fills the pipelines.
    """

    path = Path(path)

    # If we are on level one it means we are on the pipelines level.
    if level == 1:
        pipeline = Pipeline(path.name)
        pipelines.append(pipeline)
    # If we are on level two it means we are on the stages level.
    elif level == 2:
        if path.is_dir():
            pipelines[-1].append_stage(path.name)
    # If we are on level three it means we are on the jobs level.
    elif level == 3:
        name = path.stem  # Call stem to remove the file extension from the name
        stage = path.parents[0].name
        pipeline_name = path.parents[1].name
        job = Job(name, stage, pipeline_name)

        pipelines[-1].append_job(job)
    # There are no more defined levels.
    elif level > 0:
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
                "test mode",
                "srsue",
                "viavi",
                "amarisoft sdr",
                "android",
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
    Generates e2e/ci/e2e-template.yml with spec inputs, per-pipeline base and
    conditional config includes, and MR child pipeline trigger jobs.
    """

    # Path prefix for e2e/ci relative to repo root (used in local: entries)
    ci_rel = os.path.relpath(pipelines_output_path, start=stages_output_path)

    path = Path(pipelines_output_path) / "e2e-template.yml"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(generate_header())
            f.write(generate_spec())
            # Per-pipeline: unconditional base + conditional config
            f.write("include:\n")
            for name, include_path in pipeline_includes:
                f.write(f"  - local: {ci_rel}/{name}-base.yml\n")
                f.write(f"  - local: {include_path}\n")
                f.write("    rules:\n")
                f.write(f"      - if: $CI_PIPELINE_SCHEDULE_DESCRIPTION =~ /{name}/\n")
            f.write("\n")
            # MR child pipeline trigger jobs + promotion jobs, one pair per discovered pipeline
            for i, (name, include_path) in enumerate(pipeline_includes):
                if i > 0:
                    f.write("\n")
                f.write(f"{name}:\n")
                f.write("  extends: .trigger e2e\n")
                f.write("  trigger:\n")
                f.write("    include:\n")
                f.write(f"      - local: {ci_rel}/child-template.yml\n")
                f.write("        inputs:\n")
                f.write("          ocudu_path: $[[ inputs.ocudu_path ]]\n")
                f.write("          ocudu_ref: $[[ inputs.ocudu_ref ]]\n")
                f.write(f"      - local: {ci_rel}/{name}-base.yml\n")
                f.write(f"      - local: {include_path}\n")
                f.write("    strategy: mirror\n")
                f.write("    forward:\n")
                f.write("      pipeline_variables: true\n")
                f.write("\n")
                f.write(f"{name} promotion:\n")
                f.write("  extends: .ocudu promotion\n")
                f.write("  rules:\n")
                f.write(f"    - if: $CI_PIPELINE_SCHEDULE_DESCRIPTION =~ /{name}/\n")
                f.write("  variables:\n")
                f.write(f"    BRANCH: srs_{name}\n")
            print(f"🟢 Successfully created {path}")
    except IOError as e:
        print(f"⚠️ Error writing to file: {e}")


def generate_pipelines_dynamically(input_path, pipelines_output_path, stages_output_path):
    """
    Generates the needed pipelines dynamically.
    """

    pipelines: List[Pipeline] = []

    iterate_ordered_hierarchy(input_path, pipelines)

    dynamic_stages = []
    pipeline_includes = []

    base = Path(pipelines_output_path)
    base.mkdir(parents=True, exist_ok=True)

    for pipeline in pipelines:
        pipeline_path = base / f"{pipeline.get_name()}-config.yml"
        create_pipeline_file(pipeline_path, pipeline)

        dynamic_stages.extend(pipeline.get_stages())

        # Include path relative to the generated file, for the conditional include block.
        include_path = os.path.relpath(pipeline_path, start=stages_output_path)
        pipeline_includes.append((pipeline.get_name(), include_path))

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
