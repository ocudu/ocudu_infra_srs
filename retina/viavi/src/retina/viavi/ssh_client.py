#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
SSH Client Logic
"""

import logging
import shutil
import warnings
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Generator

from cryptography.utils import CryptographyDeprecationWarning

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
    import paramiko


class OS(Enum):
    """
    Operating System Enum
    """

    LINUX = "linux"
    WINDOWS = "windows"


class SSHClient:
    """
    SSH Client Logic
    """

    def __init__(self, hostname: str, username: str, password: str) -> None:
        self._hostname = hostname
        self._username = username
        self._password = password
        logging.getLogger("paramiko.transport").setLevel(logging.WARNING)

    @contextmanager
    def _ssh(self) -> Generator[paramiko.SSHClient, None, None]:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self._hostname, username=self._username, password=self._password, look_for_keys=False)
        try:
            yield ssh
        finally:
            ssh.close()

    @contextmanager
    def _sftp(self) -> Generator[paramiko.SFTPClient, None, None]:
        with self._ssh() as ssh:
            sftp = ssh.open_sftp()
            try:
                yield sftp
            finally:
                sftp.close()

    def _exec_command(self, command: str) -> int:
        with self._ssh() as ssh:
            _, stdout, _ = ssh.exec_command(command)
            return stdout.channel.recv_exit_status()

    def upload_directory(self, local_folder: str, remote_folder: str):
        """
        Upload a directory from local folder to a remote server
        """

    def download_directory(self, remote_folder: str, local_folder: str):
        """
        Download a directory from a remote server to a local folder
        """
        local_folder_path = Path(local_folder)
        if local_folder_path.exists() and local_folder_path.is_dir():
            shutil.rmtree(local_folder_path, ignore_errors=True)

        with self._sftp() as sftp:
            _download_sftp_dir(sftp, Path(remote_folder), local_folder_path)

    def _detect_os(self) -> OS:
        with self._ssh() as ssh:
            _, stdout, _ = ssh.exec_command("uname -s")
            os_type = stdout.read().decode().strip()
            if "linux" in os_type.lower():
                return OS.LINUX
            return OS.WINDOWS

    def remove_directory(self, remote_folder: str) -> int:
        """
        Remove a directory on the remote server
        """
        os_type = self._detect_os()
        if os_type == OS.LINUX:
            command = f"rm -rf {remote_folder}"
        else:
            command = f"rmdir /S /Q {remote_folder}"
        logging.info("Removing directory: %s with command %s", remote_folder, command)
        return self._exec_command(command)


def _download_sftp_dir(sftp: paramiko.SFTPClient, remote_dir: Path, local_dir: Path):
    """
    Recursively download a full directory
    """

    local_dir.mkdir(parents=True, exist_ok=True)
    for entry in sftp.listdir_attr(str(remote_dir)):
        remote_path = remote_dir.joinpath(entry.filename)
        local_path = local_dir.joinpath(entry.filename)

        if _remote_isdir(entry.st_mode):
            _download_sftp_dir(sftp, remote_path, local_path)
        else:
            try:
                sftp.get(str(remote_path), str(local_path))
            except FileNotFoundError:
                logging.warning("File not found: %s", remote_path)


def _remote_isdir(mode):
    """
    Check if the mode is a directory
    """
    return mode & 0o170000 == 0o040000
