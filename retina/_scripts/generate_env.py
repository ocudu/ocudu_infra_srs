#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Script to generate .env file with info from Retina.
It generates the .env file in the current working directory.
"""

import argparse
from contextlib import suppress
import logging
import os
import re
import shutil
import tarfile
from pathlib import Path
from string import Template

import yaml

RETINA_REGISTRY_URI = os.getenv("RETINA_REGISTRY_URI", "registry.gitlab.com/ocudu/ocudu_infra_srs/retina")
OCUDU_REGISTRY_URI = os.getenv("OCUDU_REGISTRY_URI", "registry.gitlab.com/ocudu/ocudu")
CONTAINER_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
DEFAULT_DPDK_VERSION = "24.11.2"


def load_yaml(file_path):
    """
    Load a YAML file and return its contents.
    """
    with open(file_path, encoding="utf-8") as file:
        return list(yaml.safe_load_all(file))[-1]


def main():
    """
    Main function to parse arguments and generate .env file.
    """
    logging.basicConfig(
        format="%(asctime)s \x1b[32;20m[%(levelname)s]\x1b[0m %(message)s",
        level=logging.INFO,
    )

    # argparser
    parser = argparse.ArgumentParser(description="Docker compose tool")
    parser.add_argument("--ocudu-path", required=False, help="OCUDU repo path", default=None)
    parser.add_argument("--amari-path", required=False, help="Amarisoft path", default=None)
    parser.add_argument("--dpdk-version", required=False, help="E2E DPDK version", default=DEFAULT_DPDK_VERSION)
    args = parser.parse_args()

    retina_dir = (Path(__file__).resolve().parent / "..").resolve()
    ocudu_path = None if args.ocudu_path is None else Path(args.ocudu_path).resolve()
    amari_path = None if args.amari_path is None else Path(args.amari_path).resolve()

    dpdk_version = args.dpdk_version
    if dpdk_version:
        dpdk_version = dpdk_version.split("_")[0].strip()  # Keep only the version number
    else:
        dpdk_version = DEFAULT_DPDK_VERSION

    # From CI
    root_data = load_yaml(retina_dir / "../.gitlab-ci.yml")
    root_variables = root_data["variables"]

    version_data = load_yaml(retina_dir / "version.yml")
    retina_version = version_data["variables"]["RETINA_VERSION"]

    agent_data = load_yaml(retina_dir / "agent/.gitlab-ci.yml")
    agent_variables = agent_data[".agent-docker"]["variables"]
    os_name = agent_variables["AGENT_OS_NAME"]
    os_version = agent_variables["AGENT_OS_VERSION"]

    if amari_path is None:
        logging.warning("Skipped Amarisoft support: path not provided (do it by adding --amari-path argument)")
        amarisoft_version = root_variables["AMARISOFT_VERSION"]
    else:
        amarisoft_version = manage_amari_binaries(retina_dir, amari_path)

    srsue_data = load_yaml(retina_dir / "images/srsue/.gitlab-ci.yml")
    srsue_variables = srsue_data["variables"]
    srsue_version = srsue_variables["SRSUE_VERSION"]

    open5gs_data = load_yaml(retina_dir / "images/open5gs/.gitlab-ci.yml")
    open5gs_version = open5gs_data["variables"]["OPEN5GS_VERSION"]

    ocudu_data = load_yaml(retina_dir / "images/ocudu/.gitlab-ci.yml")
    builder_image = (
        OCUDU_REGISTRY_URI + "/" + ocudu_data[".docker-builder-ocudu-base"]["variables"]["BUILDER_IMAGE_NAME"]
    )

    if ocudu_path is None:
        logging.warning(
            "Skipped Builder version support: OCUDU path not provided (do it by adding --ocudu-path argument)"
        )
        docker_builder_version = "latest"
    else:
        builder_data = load_yaml(ocudu_path / ".gitlab/ci/builders/version.yml")
        docker_builder_version = builder_data["variables"]["DOCKER_BUILDER_VERSION"]

    flexric_data = load_yaml(retina_dir / "images/flexric/.gitlab-ci.yml")
    flexric_version = flexric_data["variables"]["FLEXRIC_VERSION"]

    ntn_channel_emulator_data = load_yaml(retina_dir / "images/ntn-channel-emulator/.gitlab-ci.yml")
    ntn_channel_emulator_version = ntn_channel_emulator_data["variables"]["NTN_CHANNEL_EMULATOR_VERSION"]

    # .env creating
    current_working_directory = Path.cwd()

    env_vars = {
        "RETINA_REGISTRY_URI": RETINA_REGISTRY_URI,
        "RETINA_VERSION": retina_version,
        "AGENT_OS_NAME": os_name,
        "AGENT_OS_VERSION": os_version,
        "AMARISOFT_VERSION": amarisoft_version,
        "SRSUE_VERSION": srsue_version,
        "OPEN5GS_VERSION": open5gs_version,
        "FLEXRIC_VERSION": flexric_version,
        "NTN_CHANNEL_EMULATOR_VERSION": ntn_channel_emulator_version,
        "CONTAINER_PATH": CONTAINER_PATH,
        "OCUDU_PATH": str(ocudu_path),
        "AMARISOFT_PATH": str(amari_path),
        "DOCKER_BUILDER_VERSION": docker_builder_version,
        "BUILDER_IMAGE": builder_image,
        "DPDK_VERSION": dpdk_version,
        "UID": str(os.getuid()),
        "GID": str(os.getgid()),
    }
    for key, value in env_vars.items():
        env_vars[key] = Template(value).substitute(env_vars)  # Resolve references

    with open(current_working_directory / ".env", "w", encoding="utf-8") as env_file:
        for key, value in env_vars.items():
            env_file.write(f"{key}={value}\n")

    logging.info("Generated .env file")


def manage_amari_binaries(base_path: Path, amari_path: Path) -> str:
    """
    Manages the Amarisoft binaries by performing the following steps:
    1. Gets the version of the Amarisoft binaries.
    2. Searches for a tar.gz file matching the pattern "trx_uhd(-linux)?-{amarisoft_version}.tar.gz" in the given amari_path.
    3. Extracts the contents of the found tar.gz file.
    4. Ensures that both the tar.gz file and the extracted folder have two different names for compatibility.
    5. Copies the amari_path folder to the Amarisoft UE Retina Image context build directory.

    Args:
        base_path (Path): The base path where the Amarisoft UE Retina Image context build directory is located.
        amari_path (Path): The path where the Amarisoft binaries are located.
    Returns:
        str: A message indicating the success or failure of the operation.
    """

    if not amari_path.exists():
        raise FileNotFoundError(f"Amarisoft folder does not exist at {amari_path}")

    # Find trx_uhd driver and parse the version
    pattern = re.compile(r"trx_uhd(?:-linux)?.(\d{4}-\d{2}-\d{2})\.tar\.gz")
    matching_file = next((file for file in amari_path.iterdir() if pattern.match(file.name)), None)
    if not matching_file:
        raise FileNotFoundError(f"TRX UHD Driver does not exist in {amari_path}")

    tar_file = Path(matching_file)
    amarisoft_version = pattern.match(matching_file.name).group(1)

    # Extract the tar file
    with tarfile.open(tar_file, "r:gz") as tar:
        tar.extractall(path=amari_path)
    pattern = re.compile(rf"trx_uhd(-linux)?-{amarisoft_version}")
    matching_folder = next(
        (folder for folder in amari_path.iterdir() if folder.is_dir() and pattern.match(folder.name)), None
    )
    if not matching_folder:
        raise FileNotFoundError(f"Extracted TRX UHD Driver folder does not exist in {amari_path}")
    extracted_folder = Path(matching_folder)
    logging.info("Amarisoft TRX UHD Driver extracted to: %s", extracted_folder)

    # Ensure the tar file and the extracted folder both have two different names for compatibility
    for suffix in ["", "-linux"]:
        # tar.gz
        target_file = amari_path / f"trx_uhd{suffix}-{amarisoft_version}.tar.gz"
        with suppress(shutil.SameFileError):
            shutil.copy(tar_file, target_file)
        # Folder
        target_folder = amari_path / f"trx_uhd{suffix}-{amarisoft_version}"
        if target_folder.exists() and target_folder != extracted_folder:
            shutil.rmtree(target_folder)
        if target_folder != extracted_folder:
            shutil.copytree(extracted_folder, target_folder)

    # Copy amari folder to Amarisoft UE Retina Image context build
    amari_path_inside_context = base_path / f"images/amarisoftue/amarisoft/{amarisoft_version}"
    if amari_path != amari_path_inside_context:
        if amari_path_inside_context.exists():
            if amari_path_inside_context.is_symlink():
                amari_path_inside_context.unlink()
            else:
                shutil.rmtree(amari_path_inside_context)
        amari_path_inside_context.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(amari_path, amari_path_inside_context)
        logging.info("Amarisoft folder copied inside AmariUE Retina build context: %s", amari_path_inside_context)

    return amarisoft_version


if __name__ == "__main__":
    main()
