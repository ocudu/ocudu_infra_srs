#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Logic to save / restore artifacts from agent to client
"""

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Generator

from google.protobuf.empty_pb2 import Empty

from retina.protocol import RanStub

_ARCHIVE_FORMAT: str = "xztar"
_ARCHIVE_SUFFIX: str = ".tar.xz"
_CHUNK_SIZE: int = 1024


def calculate_folder_hash(folder: Path) -> str:
    """
    Return folder hash, cropping massive files
    """
    hash_sha1 = hashlib.sha1()
    if not folder.exists():
        raise FileNotFoundError(f"Folder to archive '{folder}' doesn't exist.")

    for file in folder.rglob("*"):
        if file.is_file():
            with file.open("rb") as file_handle:
                while True:
                    data = file_handle.read(_CHUNK_SIZE)
                    if not data:
                        break
                    hash_sha1.update(data)

    return hash_sha1.hexdigest()


def archive_artifact_folder(
    folder_to_archive_path: str,
) -> Generator[bytes, None, None]:
    """
    Return the complete report folder in a tar.gz file
    """
    logging.info("Artifact requested")
    folder_to_archive = Path(folder_to_archive_path).resolve()
    if not folder_to_archive.exists():
        raise FileNotFoundError(f"Folder to archive '{folder_to_archive}' doesn't exist.")

    with tempfile.NamedTemporaryFile(suffix=_ARCHIVE_SUFFIX) as tmp_file:
        shutil.make_archive(tmp_file.name, _ARCHIVE_FORMAT, str(folder_to_archive))
        with open(tmp_file.name + _ARCHIVE_SUFFIX, mode="rb") as file_descriptor:
            while True:
                chunk = file_descriptor.read(_CHUNK_SIZE)
                if chunk:
                    yield chunk
                else:  # The chunk was empty, which means we're at the end of the file
                    logging.info("Artifact completed")
                    return


def download_archived_artifact(stub: RanStub, folder_to_unpack_path: str):
    """
    Request archived artifacts to a stub and unpack them
    """
    folder_to_unpack = Path(folder_to_unpack_path)
    if not folder_to_unpack.exists():
        folder_to_unpack.mkdir(parents=True, exist_ok=False)
    with tempfile.NamedTemporaryFile() as tmp_file:
        for chunk in stub.DownloadArtifacts(Empty()):
            tmp_file.write(chunk.value)
        tmp_file.flush()
        shutil.unpack_archive(tmp_file.name, str(folder_to_unpack), _ARCHIVE_FORMAT, filter="data")
