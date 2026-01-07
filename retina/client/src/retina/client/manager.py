#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Default Entrypoint for the client library to be used by Retina tests
"""

import sys

from retina.client.core.artifact_service import ArtifactService
from retina.client.core.configuration_service import ConfigurationService
from retina.client.core.testbed_service import TestbedService
from retina.client.core.version_service import VersionService
from retina.client.exception import retina_except_hook
from retina.client.input.entrypoint import RetinaEntrypoint
from retina.client.output.grpc import GrpcAdaptor


class RetinaTestManager(RetinaEntrypoint):
    """
    Default Entrypoint for the client library to be used by Retina tests
    """

    def __init__(self, smart_exceptions: bool = True) -> None:
        _com_handler = GrpcAdaptor()
        super().__init__(
            testbed_service=TestbedService(_com_handler),
            parameter_service=ConfigurationService(_com_handler),
            artifact_service=ArtifactService(_com_handler),
            version_service=VersionService(_com_handler),
        )

        if smart_exceptions:
            sys.excepthook = retina_except_hook
