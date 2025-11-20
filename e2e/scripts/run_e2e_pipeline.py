#!/usr/bin/env python3
"""
Run an e2e OCUDU pipeline in Gitlab.
It allows the user to specify all the parameters.
"""


import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

# Setup those environment variables to override default ocudu_infra repository
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com")
OCUDU_INFRA_PATH = os.getenv("OCUDU_INFRA_PATH", "softwareradiosystems/ocudu_infra_srs")
OCUDU_INFRA_REF = os.getenv("OCUDU_INFRA_REF", "main")

try:
    import yaml
except ImportError:
    print("Error: PyYaml is required. Install it with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import gitlab
    from gitlab.v4.objects import Project
except ImportError:
    print("Error: Gitlab Python library is required. Install it with: pip install python_gitlab", file=sys.stderr)
    sys.exit(1)


NEEDS_REGEX = re.compile(r"Downloading artifacts for .* \((\d+)\)...", flags=re.MULTILINE)
VARIABLE_REGEX = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z \d{2}O )?(\w+)=(.*)?$", flags=re.MULTILINE
)


@dataclass
class _GitlabInput:
    description: str = ""
    type: Callable = str
    default: Any = None
    options: Optional[list] = None


_GITLAB_INPUT_TYPE_MAP = {
    "string": str,
    "number": float,
    "boolean": bool,
    "array": list,
}


def _parse_inputs_from_gitlab_ci(gitlab_ci_path: Path) -> Dict[str, _GitlabInput]:
    with gitlab_ci_path.open("r", encoding="utf-8") as f:
        yaml_text = f.read().split("---")[0]
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise RuntimeError(f"Can't extract inputs from {gitlab_ci_path}: {e}") from e

    inputs = {}
    for name, definition in parsed["spec"]["inputs"].items():
        if "type" in definition:
            definition["type"] = _GITLAB_INPUT_TYPE_MAP[definition["type"]]
        inputs[name] = _GitlabInput(**definition)
    return inputs


def _parse_args(gitlab_input_dict: Dict[str, _GitlabInput]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an e2e pipeline")
    parser.add_argument(
        "--token",
        required=True,
        type=str,
        help="Gitlab private token. "
        "See https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html#create-a-personal-access-token",
    )
    parser.add_argument(
        "--replicate",
        required=False,
        type=str,
        default="",
        help="E2E or Build Job to replicate. "
        "It can be a job name or id. Empty for no replicate (default: `%(default)s`)'",
    )
    parser.add_argument(
        "--timeout", required=False, type=int, default=300, help="Search for job timeout (default: %(default)s)"
    )
    for input_item_name, input_item in gitlab_input_dict.items():
        arg_name = f"--{input_item_name.replace('_', '-')}"
        arg_kwargs = {
            "required": input_item.default is None,
            "type": input_item.type,
            "help": input_item.description
            + (f" (default: `{input_item.default}`)" if input_item.default is not None else ""),
            "default": argparse.SUPPRESS,
        }
        if input_item.type is list:
            arg_kwargs["nargs"] = "+"
            arg_kwargs["type"] = str
        if input_item.options:
            arg_kwargs["choices"] = input_item.options
        parser.add_argument(arg_name, **arg_kwargs)  # type: ignore

    parser.add_argument("--yes", action="store_true", help="Disable interactivity (default: false)")
    parser.add_argument("--dryrun", action="store_true", help="Skip pipeline creation (default: false)")

    return parser.parse_args()


def _search_job(project_array: Sequence[Project], job_name: str, timeout: int) -> Dict[str, str]:
    variable_dict = {}

    print("⏳ Looking for the job...")

    # Try to parse as integer ID
    try:
        job_id = int(job_name)
        for project in project_array:
            try:
                job = project.jobs.get(job_id)
                variable_dict.update(_extract_variables_from_job(project, job.id))
            except gitlab.exceptions.GitlabGetError:
                continue
        print(
            f"⛔ Could not found job with id {job_id} in projects "
            f"{' and '.join([project.web_url for project in project_array])} ⛔"
        )
        sys.exit(1)
    except ValueError:
        # Not an integer, search by name
        time_to_reach = time.time() + timeout
        for project in project_array:
            for pipeline in project.pipelines.list(iterator=True, source="schedule"):
                for job in pipeline.jobs.list(iterator=True):
                    if job.name == job_name:
                        variable_dict.update(_extract_variables_from_job(project, job.id))
                        if not variable_dict:
                            continue  # If the variable dict is empty, keep searching
                        return variable_dict
                    if time.time() >= time_to_reach:
                        print(
                            "⛔ Timeout reached looking for the job. "
                            "Please review job's name or increase this timeout by setting --timeout ⛔"
                        )
                        sys.exit(1)

    return variable_dict


def _extract_variables_from_job(project: Project, job_id: int) -> Dict[str, str]:
    job = project.jobs.get(job_id)
    if "driver" in job.name:
        return {}  # Filter out driver jobs
    job_log = job.trace().decode("utf-8")
    if not job_log:
        return {}  # Filter out jobs without output - we can't extract variables
    print(f'🟢 Job "{job.name}" found (id: {job.id})')

    variable_dict = {}
    for needs_job_id in re.findall(NEEDS_REGEX, job_log):
        variable_dict.update(_extract_variables_from_job(project, needs_job_id))
    for item in re.findall(VARIABLE_REGEX, job_log):
        key, value = item
        if key.isupper() and "$" not in value:
            variable_dict[key] = value.strip()

    return variable_dict


def _require_user_input(gitlab_input_dict: Dict[str, _GitlabInput]):
    print(
        "📝 Fill the inputs. Press enter to keep the value between brackets. "
        "You can skip this confirmation adding --yes flag to the call."
    )
    for input_item_name, input_item in gitlab_input_dict.items():
        while True:
            user_value = input(f" - {input_item_name} [{input_item.default}]: ")
            if user_value:
                # Cast types
                user_value = user_value.strip()
                if input_item.type is list:
                    user_value = json.loads(user_value)
                elif input_item.type is str:
                    user_value = user_value.replace("'", "").replace('"', "")
                else:
                    user_value = input_item.type(user_value)
                # Validate options
                if input_item.options and user_value not in input_item.options:
                    print(f'   ❌ Invalid option "{user_value}". Valid options are: {input_item.options}')
                    continue
                # Set value
                input_item.default = user_value
            break


def _get_project(token: str, project: str) -> Project:
    gl = gitlab.Gitlab(GITLAB_URL, private_token=token)
    return gl.projects.get(project)


def _create_pipeline(project: Project, branch: str, gitlab_input_dict: Dict[str, _GitlabInput], dryrun: bool):
    input_dict = {}

    print("⏩ Creating pipeline with inputs:")
    for input_item_name, input_item in gitlab_input_dict.items():
        print(f"  - {input_item_name}={input_item.default}")
        input_dict[input_item_name] = input_item.default
    print("")

    if not dryrun:
        pipeline = project.pipelines.create({"ref": branch, "inputs": input_dict})
        print("✅ Pipeline created: ", pipeline.web_url)
    else:
        print("🟰 Pipeline creation skipped due to dryrun mode")


def _main():
    gitlab_input_dict = _parse_inputs_from_gitlab_ci(Path(__file__).parent.parent.parent / ".gitlab-ci.yml")
    args = _parse_args(gitlab_input_dict)
    print("")

    # Replicate Job
    infra_project = _get_project(token=args.token, project=OCUDU_INFRA_PATH)
    ocudu_project = _get_project(
        token=args.token, project=getattr(args, "ocudu_path", gitlab_input_dict.get("ocudu_path").default)
    )
    if args.replicate:
        variables_dict = _search_job((infra_project, ocudu_project), args.replicate, args.timeout)
        # Fill with replicated values
        for input_item_name, input_item in gitlab_input_dict.items():
            if input_item_name.upper() in variables_dict:
                input_item.default = variables_dict[input_item_name.upper()]

    # Overwrite values with CLI args
    for input_item_name, input_item in gitlab_input_dict.items():
        if hasattr(args, input_item_name):
            input_item.default = getattr(args, input_item_name)
            if input_item.type is str:
                input_item.default = input_item.default.strip().replace("'", "").replace('"', "")

    # Allow user to input values in case interactivity is enabled
    if not args.yes:
        _require_user_input(gitlab_input_dict)

    # Create pipeline
    try:
        _create_pipeline(
            project=infra_project, branch=OCUDU_INFRA_REF, gitlab_input_dict=gitlab_input_dict, dryrun=args.dryrun
        )
    except gitlab.exceptions.GitlabCreateError as e:
        print(f"❌ Failed to create pipeline: {e.error_message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _main()
