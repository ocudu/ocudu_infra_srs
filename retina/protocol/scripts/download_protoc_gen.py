#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

import gzip
from pathlib import Path
import platform
import shutil
import tarfile
import tempfile

import requests


def main():
    version = "1.5.1"
    platform_name = platform.system().lower()
    arch_name = (
        "amd64"
        if platform.machine().lower().replace("_", "").replace("-", "") == "x8664"
        else "arm64"
    )
    bin_name = "protoc-gen-doc"

    dst_path = Path(__file__).parent.parent.joinpath(f".{bin_name}").resolve()
    dst_path.mkdir(parents=True, exist_ok=True)

    temp_folder = Path(tempfile.mkdtemp())
    tar_gz_file = temp_folder.joinpath(f"{bin_name}.tar.gz")
    tar_file = temp_folder.joinpath(f"{bin_name}.tar")

    # Download it
    response = requests.get(
        f"https://github.com/pseudomuto/{bin_name}/releases/download/"
        f"v{version}/{bin_name}_{version}_{platform_name}_{arch_name}.tar.gz",
        allow_redirects=True,
        timeout=30,
    )

    # Write in tar.gz
    with tar_gz_file.open(mode="wb") as fd:
        fd.write(response.content)

    # gz decrompress
    with gzip.open(str(tar_gz_file)) as fd:
        with open(str(tar_file), "wb") as f_out:
            shutil.copyfileobj(fd, f_out)

    # tar decompress
    with tarfile.open(str(tar_file)) as fd:
        fd.extractall(str(temp_folder))

    shutil.move(str(temp_folder.joinpath(bin_name)), str(dst_path.joinpath(bin_name)))

    shutil.rmtree(str(temp_folder), ignore_errors=True)


if __name__ == "__main__":
    main()
