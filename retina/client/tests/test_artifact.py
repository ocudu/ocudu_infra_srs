#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, call
from retina.client.core.artifact_service import ArtifactService

from retina.client.core.communication_port import CommunicationPort
from retina.client.core.testbed_service import TestbedService

from .test_testbed import VALID_5GC, VALID_GNB, VALID_UE, VALID_UE_2, VALID_UE_3


class DownloadArtifacts(unittest.TestCase):
    MULTIPLE_TRIES = 30

    def setUp(self):
        self.backend = CommunicationPort()
        self.backend.create_client = MagicMock(
            side_effect=lambda resource_type, *com_args: {
                "type": resource_type,
                "com_args": com_args,
            }
        )
        self.backend.close_client = MagicMock()
        self.backend.download_artifacts = MagicMock()
        self.backend.get_artifact_id = MagicMock(side_effect=lambda stub: str(id(stub)))
        self.testbed_use_case = TestbedService(com_handler=self.backend)
        self.artifact_use_case = ArtifactService(com_handler=self.backend)
        self._temp_folder = TemporaryDirectory()
        self.temp_folder = Path(self._temp_folder.name)

    def tearDown(self) -> None:
        self.testbed_use_case.close_all()
        self._temp_folder.cleanup()

    def assertEmptyFolder(self, folder: Path):
        self.assertEqual(not any(folder.iterdir()), True)

    def test_given_no_testbed_when_download_all_then_should_not_fail(self):
        self.artifact_use_case.download_all_artifacts(str(self.temp_folder))
        self.backend.download_artifacts.assert_not_called()
        self.assertEmptyFolder(self.temp_folder)

    def test_given_invalid_client_when_download_it_then_should_fail(self):
        for invalid_client in (None, ""):
            with self.subTest(invalid_client=invalid_client):
                self.assertRaises(
                    KeyError,
                    self.artifact_use_case.download_client_artifacts,
                    invalid_client,
                    str(self.temp_folder),
                )
        self.assertEmptyFolder(self.temp_folder)

    def test_given_valid_client_when_download_it_then_should_not_fail(
        self,
    ):
        testbed = [VALID_UE, VALID_UE_2, VALID_UE_3]
        for index, tb_item in enumerate(testbed):
            with self.subTest(index=index):
                self.testbed_use_case.validate_testbed({"id": "id", "node_list": testbed})
                self.backend.download_artifacts.reset_mock()
                client = self.testbed_use_case.get_ue(index)
                self.artifact_use_case.download_client_artifacts(client, str(self.temp_folder))
                self.backend.download_artifacts.assert_called_once_with(
                    client, str(self.temp_folder.joinpath(tb_item["name"]))
                )

    def test_given_valid_client_when_download_all_then_should_and_not_fail(
        self,
    ):
        for index, tb_item in enumerate((VALID_UE, VALID_UE_2, VALID_UE_3)):
            with self.subTest(index=index):
                self.testbed_use_case.validate_testbed({"id": "id", "node_list": [tb_item]})
                self.backend.download_artifacts.reset_mock()
                client = self.testbed_use_case.get_ue()
                self.artifact_use_case.download_all_artifacts(str(self.temp_folder))
                self.backend.download_artifacts.assert_called_once_with(
                    client, str(self.temp_folder.joinpath(tb_item["name"]))
                )

    def test_given_multiple_valid_clients_when_download_all_then_should_and_not_fail(
        self,
    ):
        testbed = [VALID_UE, VALID_GNB, VALID_5GC]
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": testbed})
        client_ue = self.testbed_use_case.get_ue()
        client_gnb = self.testbed_use_case.get_gnb()
        self.artifact_use_case.download_all_artifacts(str(self.temp_folder))
        self.backend.download_artifacts.assert_has_calls(
            (
                call(client_ue, str(self.temp_folder.joinpath(VALID_UE["name"]))),
                call(client_gnb, str(self.temp_folder.joinpath(VALID_GNB["name"]))),
            ),
            any_order=True,
        )
        self.assertRaises(
            AssertionError,
            self.backend.close_client.assert_any_call,
            self.testbed_use_case.get_5gc(),
            str(self.temp_folder.joinpath(VALID_5GC["name"])),
        )

    def test_given_multiple_clients_same_type_when_get_one_in_middle_and_download_all_then_should_download_all_below_it(
        self,
    ):
        testbed = [VALID_UE, VALID_UE_2, VALID_UE_3]
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": testbed})
        client_1 = self.testbed_use_case.get_ue(1)
        self.artifact_use_case.download_all_artifacts(str(self.temp_folder))
        client_0 = self.testbed_use_case.get_ue(0)
        client_2 = self.testbed_use_case.get_ue(2)
        self.backend.download_artifacts.assert_has_calls(
            (
                call(client_0, str(self.temp_folder.joinpath(VALID_UE["name"]))),
                call(client_1, str(self.temp_folder.joinpath(VALID_UE_2["name"]))),
            ),
            any_order=True,
        )
        self.assertRaises(
            AssertionError,
            self.backend.close_client.assert_any_call,
            client_2,
            str(self.temp_folder.joinpath(VALID_UE_3["name"])),
        )

    def test_given_valid_client_when_download_it_multiple_time_then_should_do_it_every_time(
        self,
    ):
        testbed = [VALID_UE, VALID_GNB, VALID_5GC]
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": testbed})
        client = self.testbed_use_case.get_ue()
        for times in range(1, self.MULTIPLE_TRIES + 1):
            with self.subTest(times=times):
                self.artifact_use_case.download_all_artifacts(str(self.temp_folder))
                self.backend.download_artifacts.assert_has_calls(
                    ((call(client, str(self.temp_folder.joinpath(VALID_UE["name"]))),) * times),
                )

    def test_given_valid_client_when_download_all_multiple_then_should_do_it_every_time(
        self,
    ):
        testbed = [VALID_UE, VALID_GNB, VALID_5GC]
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": testbed})
        client_ue = self.testbed_use_case.get_ue()
        client_gnb = self.testbed_use_case.get_gnb()
        client_5gc = self.testbed_use_case.get_5gc()
        for times in range(1, self.MULTIPLE_TRIES + 1):
            with self.subTest(times=times):
                self.artifact_use_case.download_all_artifacts(str(self.temp_folder))
                self.backend.download_artifacts.assert_has_calls(
                    (
                        (
                            call(
                                client_ue,
                                str(self.temp_folder.joinpath(VALID_UE["name"])),
                            ),
                            call(
                                client_gnb,
                                str(self.temp_folder.joinpath(VALID_GNB["name"])),
                            ),
                            call(
                                client_5gc,
                                str(self.temp_folder.joinpath(VALID_5GC["name"])),
                            ),
                        )
                        * times
                    ),
                )

    def test_given_closed_client_when_download_it_then_should_fail(self):
        testbed = [VALID_UE, VALID_GNB, VALID_5GC]
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": testbed})
        client_ue = self.testbed_use_case.get_ue()
        self.testbed_use_case.close_client(client_ue)
        self.assertRaises(
            KeyError,
            self.artifact_use_case.download_client_artifacts,
            client_ue,
            str(self.temp_folder),
        )
        self.backend.download_artifacts.assert_not_called()

    def test_given_some_closed_clients_and_some_open_when_download_all_then_should_skip_the_closed_ones(
        self,
    ):
        testbed = [VALID_UE, VALID_GNB, VALID_5GC]
        self.testbed_use_case.validate_testbed({"id": "id", "node_list": testbed})
        client_ue = self.testbed_use_case.get_ue()
        client_gnb = self.testbed_use_case.get_gnb()
        self.testbed_use_case.close_client(client_ue)
        self.artifact_use_case.download_all_artifacts(str(self.temp_folder))
        self.backend.download_artifacts.assert_called_once_with(
            client_gnb, str(self.temp_folder.joinpath(VALID_GNB["name"]))
        )


if __name__ == "__main__":
    unittest.main()
