# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Artifact handling
"""

import logging
import os
from pathlib import Path
from typing import Dict, List

from retina.protocol import RanStub

from retina.client.core import storage
from retina.client.core.artifact_port import ArtifactPort


class ArtifactService(ArtifactPort):
    """
    Artifact handling
    """

    def download_client_artifacts(self, stub: RanStub, report_folder: str) -> None:
        for client_array in storage.clients.values():
            for client in client_array:
                if client.stub is stub and not client.closed:
                    self._com_handler.download_artifacts(
                        client.stub,
                        str(Path(report_folder).joinpath(client.name).resolve()),
                    )
                    return
        raise KeyError("Client was never created or it's already closed")

    def download_all_artifacts(self, report_folder: str) -> None:
        logging.debug("Downloading artifacts")
        artifact_id_dict: Dict[str, List[storage.Client]] = {}
        for client_array in storage.clients.values():
            for client in client_array:
                artifact_id = self._com_handler.get_artifact_id(client.stub)
                if artifact_id not in artifact_id_dict:
                    artifact_id_dict[artifact_id] = []
                artifact_id_dict[artifact_id].append(client)

        for _, client_array in artifact_id_dict.items():
            client_names = [client.name for client in client_array]
            folder_name = os.path.commonprefix(client_names)
            if len(client_array) > 2:
                folder_name += client_names[0][len(folder_name) :] + "-to-" + client_names[-1][len(folder_name) :]

            client = client_array[0]
            if not client.closed:
                logging.debug("Downloading artifacts from %s", folder_name)
                self._com_handler.download_artifacts(
                    client.stub,
                    str(Path(report_folder).joinpath(folder_name).resolve()),
                )
