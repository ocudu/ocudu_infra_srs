# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Viavi core
"""

import io
import logging
import random
import string
import time
import warnings
from contextlib import suppress
from pathlib import Path

from cryptography.utils import CryptographyDeprecationWarning

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
    import paramiko


# new exception
class ViaviCoreError(Exception):
    """
    Viavi core error
    """


def generate_random_string(long: int) -> str:
    """
    Generate a random string
    """
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(long))


def _start_core(ssh: paramiko.SSHClient):
    """
    Start the 5G core
    """
    logging.info("Starting the 5G core")
    stdout, error = _execute_script(ssh, "start")
    logging.info("5G core started")
    return stdout, error


def _stop_core(ssh: paramiko.SSHClient):
    """
    Stop the 5G core
    """
    logging.info("Stopping the 5G core")
    stdout, error = _execute_script(ssh, "stop")
    logging.info("5G core stopped")
    return stdout, error


def _execute_script(ssh: paramiko.SSHClient, mode: str):
    """
    Start the 5G core
    """
    folder_path = "/tmp"
    filename = f"{generate_random_string(10)}.ntl"
    remote_file_path = f"{folder_path}/{filename}"
    local_file_path = str(Path(__file__).resolve().parent / f"{mode}.ntl")

    # copy script
    sftp = ssh.open_sftp()
    sftp.put(local_file_path, remote_file_path)

    # execute script
    cmd = f"cd {folder_path}; ng40test {filename}"
    output, error = _execute_command(ssh, cmd)
    time.sleep(20)

    # remove script
    sftp.remove(remote_file_path)

    return output, error


def _execute_command(ssh: paramiko.SSHClient, command: str):
    """
    Execute a command on the remote server
    """
    _, stdout, stderr = ssh.exec_command(command)
    output = stdout.read().decode()
    error = stderr.read().decode()
    return output, error


def _read_private_key(ssh: paramiko.SSHClient, path: str):
    """
    Read the private key from the remote server
    """
    sftp = ssh.open_sftp()
    with sftp.file(path, "r") as f:
        key_data = f.read().decode("utf-8")
    return key_data


def _create_ssh() -> paramiko.SSHClient:
    """
    Create a new SSH client
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return ssh


CONNECTION_DEF = [
    {
        "hostname": "192.168.10.200",
        "username": "viavi",
        "password": "viavi",
    },
    {
        "hostname": "172.111.111.101",
        "username": "viavi",
        "password": "",
    },
]


def restart_core(hostname: str, username: str, password: str):
    """
    Restart the 5G core
    """
    try:
        #######################################################################
        # Connection to first server
        #######################################################################
        ssh1 = _create_ssh()
        ssh1.connect(hostname, username=username, password=password, look_for_keys=False, allow_agent=False)

        #######################################################################
        # Connection to second server
        #######################################################################
        transport1 = ssh1.get_transport()
        if not transport1:
            raise ViaviCoreError("Error connecting to the first server")
        channel1 = transport1.open_channel("direct-tcpip", (CONNECTION_DEF[0]["hostname"], 2222), ("127.0.0.1", 0))

        ssh2 = _create_ssh()
        ssh2.connect(
            CONNECTION_DEF[0]["hostname"],
            username=CONNECTION_DEF[0]["username"],
            password=CONNECTION_DEF[0]["password"],
            sock=channel1,
            look_for_keys=False,
            allow_agent=False,
        )

        #######################################################################
        # Connection to third server
        #######################################################################
        transport2 = ssh2.get_transport()
        if not transport2:
            raise ViaviCoreError("Error connecting to the first server")
        channel2 = transport2.open_channel("direct-tcpip", (CONNECTION_DEF[1]["hostname"], 22), ("127.0.0.1", 0))

        # Read private key
        key_path = "/home/viavi/.ssh/id_rsa"
        private_key = paramiko.RSAKey(file_obj=io.StringIO(_read_private_key(ssh2, key_path)))

        ssh3 = _create_ssh()
        ssh3.connect(
            CONNECTION_DEF[1]["hostname"],
            username=CONNECTION_DEF[1]["username"],
            sock=channel2,
            pkey=private_key,
        )

        #######################################################################
        # Command
        #######################################################################
        _, error = _stop_core(ssh3)
        if error:
            logging.error("Error stopping core: %s", error)

        _, error = _start_core(ssh3)
        if error:
            logging.error("Error starting core: %s", error)
    # pylint: disable=broad-except
    except Exception as e:
        logging.error("Error: %s", e)
    finally:
        with suppress(Exception):
            ssh3.close()
        with suppress(Exception):
            ssh2.close()
        with suppress(Exception):
            ssh1.close()
