#!/usr/bin/env python3
"""
Run an e2e OCUDU pipeline in Gitlab.
It will run a viavi test specified by the user, allowing them to customize some parameters like gnb options.
"""

import argparse
import os
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Dict

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
except ImportError:
    print("Error: Gitlab Python library is required. Install it with: pip install python_gitlab", file=sys.stderr)
    sys.exit(1)


# pylint: disable=too-many-instance-attributes
@dataclass
class _TestDefinition:
    """ """

    id: str = ""
    campaign_filename: str = ""
    test_name: str = ""
    description: str = ""
    gnb_extra_config: Dict = field(default_factory=dict)


@dataclass
class _BuildDefinition:
    tag: str
    os: str
    compiler: str
    target: str
    build_args: str
    dpdk_version: str
    uhd_version: str


BUILD_DEFINITIONS: Dict[str, _BuildDefinition] = {
    "standard": _BuildDefinition(
        tag="amd64-avx2-avx512",
        os="ubuntu-24.04",
        compiler="gcc",
        target="gnb_split_7_2",
        build_args="-DCMAKE_BUILD_TYPE=Release -DFORCE_DEBUG_INFO=True -DENABLE_UHD=False -DENABLE_DPDK=True "
        '-DENABLE_ZEROMQ=False -DENABLE_FFTW=False -DENABLE_MKL=True -DMARCH="x86-64-v4"',
        dpdk_version="23.11.4_avx512",
        uhd_version="",
    ),
    "rtsan": _BuildDefinition(
        tag="amd64-avx2-avx512",
        os="ubuntu-24.04-rtsan",
        compiler="clang",
        target="gnb_split_7_2",
        build_args="-DCMAKE_BUILD_TYPE=Release -DFORCE_DEBUG_INFO=True -DENABLE_UHD=False -DENABLE_DPDK=True "
        '-DENABLE_ZEROMQ=False -DENABLE_FFTW=False -DENABLE_MKL=True -DMARCH="x86-64-v4" '
        "-DENABLE_RTSAN=True -DENABLE_WERROR=False",
        dpdk_version="23.11.4_avx512",
        uhd_version="",
    ),
}


# pylint: disable=too-many-instance-attributes
@dataclass
class _ArgsDefinition:
    """ """

    ocudu_path: str = ""
    ocudu_ref: str = ""
    token: str = ""
    branch: str = ""
    testid: str = ""
    campaign_path: str = ""
    test_name: str = ""
    timeout: int = 0
    gnb_cli: str = ""
    build_mode: str = ""


def _convert_extra_config_into_command(extra_config: dict) -> str:
    """
    Convert extra config into command
    """
    cmd_args = ""
    for key, value in sorted(extra_config.items(), key=lambda item: isinstance(item[1], dict)):
        if isinstance(value, dict):
            cmd_args += f"{key} " + _convert_extra_config_into_command(value)
        else:
            cmd_args += f"--{key}={value} "
    return cmd_args


def _get_viavi_tests() -> Dict[str, _TestDefinition]:
    viavi_test_declaration = (
        pathlib.Path(__file__).parent.parent / "tests" / "viavi" / "test_declaration.yml"
    ).resolve()
    with open(viavi_test_declaration, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    test_dict = {}
    for test in data["tests"]:
        test_definition = _TestDefinition()
        test_definition.id = test["id"]
        test_definition.campaign_filename = test["campaign_filename"]
        test_definition.test_name = test["test_name"]
        test_definition.description = test.get("description", "")
        test_definition.gnb_extra_config = test.get("gnb_extra_config", "")
        test_dict[test_definition.id] = test_definition

    return test_dict


def _validate_args(args) -> _ArgsDefinition:
    args_definition = _ArgsDefinition()
    args_definition.ocudu_path = args.ocudu_path
    args_definition.ocudu_ref = args.ocudu_ref
    args_definition.token = args.token
    args_definition.testid = args.testid
    args_definition.campaign_path = args.campaign
    args_definition.test_name = args.test
    args_definition.timeout = args.timeout
    args_definition.gnb_cli = args.gnb_cli
    args_definition.build_mode = args.build_mode

    print("")

    if (args_definition.testid and args_definition.test_name) or (  # id and name set
        not args_definition.testid and not args_definition.test_name  # id / name not set
    ):
        print(
            "You either select an already existing test with --testid "
            "or provide a new one by using --test (+ --campaign)."
        )
        sys.exit(1)

    return args_definition


def _run_test(args_definition: _ArgsDefinition, test_definition: _TestDefinition):
    build_definition = BUILD_DEFINITIONS[args_definition.build_mode]
    timeout = args_definition.timeout if args_definition.timeout else 972800

    retina_launcher_args = (
        f'--viavi-manual-campaign-filename "{test_definition.campaign_filename}" '
        f'--viavi-manual-test-name "{test_definition.id}" --viavi-manual-test-timeout {timeout}'
    )
    if args_definition.gnb_cli:
        retina_launcher_args += f' --viavi-manual-gnb-arguments "{args_definition.gnb_cli}"'
        if test_definition.gnb_extra_config:
            print(
                "⚠️  Using gnb-cli overwrites the configuration defined in the test_declaration.yml for the test. "
                "Please review your new config carefully!!"
            )
            print("⚠️  OLD configuration: ", _convert_extra_config_into_command(test_definition.gnb_extra_config))
            print("⚠️  NEW configuration: ", args_definition.gnb_cli)
            print("")
            if input("Do you want to continue with the new configuration? (yes/no): ").strip().lower() not in (
                "y",
                "yes",
            ):
                print("Exiting as per user request.")
                sys.exit(0)
            print("")

    input_dict = {
        "ocudu_path": args_definition.ocudu_path,
        "ocudu_ref": args_definition.ocudu_ref,
        "infrastructure_tag": build_definition.tag,
        "os": build_definition.os,
        "srs_target": build_definition.target,
        "compiler": build_definition.compiler,
        "build_args": build_definition.build_args,
        "dpdk_version": build_definition.dpdk_version,
        "uhd_version": build_definition.uhd_version,
        "test_mode": "none",
        "e2e_tag": "new-retina-e2e-amd64",
        "group": "viavi",
        "testbed": "viavi",
        "markers": "viavi_manual",
        "file_or_dir": "",
        "keywords": "",
        "retina_args": "gnb.all.pcap=True gnb.all.rlc_enable=True gnb.all.rlc_rb_type=srb",
        "launcher_args": retina_launcher_args,
    }

    print(f"Creating Viavi pipeline for branch {args_definition.ocudu_ref}...")
    if args_definition.testid:
        print(f"    - Test ID: {test_definition.id}")
    else:
        print(f"    - Custom test: {test_definition.campaign_filename} / {test_definition.test_name}")
    print(f"    - Build mode: {args_definition.build_mode}")
    print(f"      - OS {build_definition.os}")
    print(f"      - BUILD_ARGS {build_definition.build_args}")
    print(f"      - DPDK_VERSION {build_definition.dpdk_version}")

    gl = gitlab.Gitlab(GITLAB_URL, private_token=args_definition.token)
    project = gl.projects.get(OCUDU_INFRA_PATH)
    pipeline = project.pipelines.create({"ref": OCUDU_INFRA_REF, "inputs": input_dict})

    pipeline_url = pipeline.web_url

    print(f"🟢 Pipeline created: {pipeline_url}")


def main():
    """
    Entrypoint runner.
    """
    test_dict = _get_viavi_tests()

    parser = argparse.ArgumentParser(
        description="Run a Viavi test in Gitlab CI.\n"
        " A) Use --testid to select an existing test from the CI.\n"
        '    $ run_viavi_pipeline.py --testid "1UE ideal UDP bidirectional" ... \n'
        " B) Use --campaign and --test to select any test defined in Viavi.\n"
        '    $ run_viavi_pipeline.py --test "32UE ideal UDP attach-detach with traffic conservative"'
        ' [--campaign "C:\\ci\\CI 4x4 ORAN-FH-complete.xml"] ...',
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Common
    parser.add_argument(
        "--token",
        help="[REQUIRED] Gitlab private token: "
        "https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html#create-a-personal-access-token",
        required=True,
    )
    parser.add_argument(
        "--ocudu-path", help="OCUDU repository path. (default: `%(default)s`)'", default="softwareradiosystems/srsgnb"
    )
    parser.add_argument("--ocudu-ref", help="OCUDU reference branch or tag. (default: `%(default)s`)", default="dev")
    parser.add_argument(
        "--build-mode",
        help='Build mode for gnb. Default: "rtsan"',
        default="rtsan",
        choices=BUILD_DEFINITIONS.keys(),
    )
    parser.add_argument(
        "--timeout", help="Timeout in seconds for the test. If not specified, it will use the timeout defined in Viavi"
    )

    # Defined tests
    parser.add_argument(
        "--testid",
        help="Testid in the campaign.",
        metavar="{" + " | ".join(test_dict.keys()) + "}",
        choices=test_dict.keys(),
    )

    # Custom tests
    parser.add_argument(
        "--campaign",
        help="Campaign path. [Only for custom tests]. Default: CI campaign",
        default=tuple(test_dict.values())[0].campaign_filename,
    )
    parser.add_argument("--test", help="Test name. [Only for custom tests]")

    parser.add_argument(
        "--gnb-cli",
        default="",
        help='Arguments passed to the gnb binary. E.g: "log --all_level=info". '
        "This overwrites any argument in the test_declaration.yml file.",
    )

    args_definition = _validate_args(parser.parse_args())
    if args_definition.testid:
        _run_test(args_definition, test_dict[args_definition.testid])
    else:
        _run_test(
            args_definition,
            _TestDefinition(
                id=args_definition.test_name,
                campaign_filename=args_definition.campaign_path,
                test_name=args_definition.test_name,
                description="Custom test",
                gnb_extra_config={},
            ),
        )


if __name__ == "__main__":
    main()
