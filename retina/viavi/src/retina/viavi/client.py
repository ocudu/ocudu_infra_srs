# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Viavi API
"""

import contextlib
import logging
import os
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Generator, Optional, Tuple

from requests import HTTPError

from retina.viavi.kpis import ViaviKPIs, ViaviLinkData, ViaviProcedureFailure
from retina.viavi.reporter import (
    create_procedure_html_report,
    KOS_HEADERS,
    parse_dl_ul_metrics,
    parse_procedure_table,
    parse_warnings,
)
from retina.viavi.rest_client import DEFAULT_TIMEOUT, delete, get, post
from retina.viavi.ssh_client import SSHClient
from retina.viavi.viavi_core import restart_core


class CampaignStatusEnum(Enum):
    """
    Enum with possible campaign status
    """

    NOTHING = "No Campaign in progress"
    WAITING = "AUTOMATION_RUN Start"
    RUNNING = "AUTOMATION_RUN"
    FAIL = "FAIL"
    PASS = "PASS"

    def __str__(self) -> str:
        return self.name.capitalize()


@dataclass
class CampaignInfo:
    """
    Information about a campaign
    """

    status: CampaignStatusEnum = CampaignStatusEnum.NOTHING
    progress: int = 0
    message: str = ""
    test_name: str = ""


# pylint: disable=too-many-instance-attributes
class Viavi(SSHClient):
    """
    Viavi Controller
    """

    TMA_NUMBER: str = "0001"

    _CAMPAIGN_RUNNING_REGEX: re.Pattern = re.compile(r"I: AUTOMATION_RUN (.*?) \"(.*?)\" (\d+) (\d+)%")
    _TEST_PASSED_REGEX: re.Pattern = re.compile(r"I: AUTOMATION_RUN \"(.*?)\" \d+ PASS$")
    _TEST_FAILED_REGEX: re.Pattern = re.compile(r"I: AUTOMATION_RUN \"(.*?)\" \d+ FAIL$")
    _CAMPAIGN_PASSED_REGEX: re.Pattern = re.compile(r"I: AUTOMATION_RUN (.*?) \"(.*?)\" PASS$")
    _CAMPAIGN_FAILED_REGEX: re.Pattern = re.compile(r"I: AUTOMATION_RUN (.*?) \"(.*?)\" FAIL \"(.*?)(?:\")?$")

    _REPORT_TIMEOUT: int = 30 * 60

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        tma_path: str,
        tma_profile: str,
        address: str,
        port: int,
        username: str,
        password: str,
        amf_address: str = "localhost",
        amf_port: int = 38412,
        **kwargs,
    ):
        super().__init__(hostname=address, username=username, password=password, **kwargs)
        self.url_base = f"http://{address}:{port}/rtc/v2"
        self._amf_address = amf_address
        self._amf_port = amf_port
        self._tma_path = tma_path
        self._tma_profile = tma_profile
        self._kpis = ViaviKPIs(
            failures=[],
            dl_data=_create_viavi_link_data({}),
            ul_data=_create_viavi_link_data({}),
            warning_array=["Using default KPIs: Report not found or invalid"],
        )

    def get_core_definition(self) -> Tuple[str, int]:
        """
        Returns ip and port for the 5gc core
        """
        return self._amf_address, self._amf_port

    ############################################################################
    # TMA
    ############################################################################
    def kill_tma(self) -> None:
        """
        Kill the TMA process
        """
        try:
            command = 'taskkill /IM "TmaApplication.exe" /F'
            self._exec_command(command)
        except Exception as exc:  # pylint: disable=broad-except
            logging.warning("Error killing TMA: %s", exc)

    def create_tma(self, *args, **kwargs) -> None:
        """
        Create a TMA instance
        """
        restart_core(self._hostname, self._username, self._password)

        try:
            tma_id = post(
                f"{self.url_base}/tmas",
                {
                    "TMA_TYPE": 1,
                    "TMA_PROFILE": self._tma_profile,
                    "TMA_PATH": self._tma_path,
                },
                *args,
                **kwargs,
            )
        except TimeoutError as exc:
            raise TimeoutError("Viavi API call timed out while waiting for TMA to be created") from exc

        get(
            f"{self.url_base}/tmas/{tma_id}",
        )

    def delete_tma(self, *args, **kwargs) -> None:
        """
        Delete a TMA instance
        """
        with contextlib.suppress(Exception):
            delete(f"{self.url_base}/tmas/{self.TMA_NUMBER}", *args, **kwargs)
        self.kill_tma()

    ############################################################################
    # Campaigns
    ############################################################################
    def schedule_campaign(self, filename: str, test_name: Optional[str] = None, **kwargs) -> str:
        """
        Schedule a campaign
        @param filename: Campaign filename
        @returns Campaign name
        """
        try:
            return post(
                f"{self.url_base}/tmas/{self.TMA_NUMBER}/campaigns/actions/schedule",
                {
                    "FILE_PATH": filename,
                    "ITERATION_COUNT": 1,
                    "ACTION_ON_EVENT": 2,
                    **({"TESTS_SELECTION_BY_NAME": [test_name]} if test_name is not None else {}),
                },
                **kwargs,
            )
        except TimeoutError as exc:
            raise RuntimeError("Viavi API call timed out while waiting for campaign to be scheduled") from exc

    def run_campaign(self, campaign_name: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        """
        Run a campaign by name
        """
        timeout_handler = TimeoutHandler(timeout, "Campaign did not start in the expected timeout")
        try:
            result = post(
                f"{self.url_base}/tmas/{self.TMA_NUMBER}/campaigns/actions/run",
                {
                    "CAMPAIGN_NAME": campaign_name,
                },
                timeout=timeout_handler.get_remaining_timeout(),
            )
        except TimeoutError as exc:
            raise RuntimeError("Viavi API call timed out while waiting for campaign to start") from exc

        while timeout_handler.not_reached():
            try:
                self.get_running_campaign_info(timeout_handler.get_remaining_timeout())
                break
            except HTTPError:
                time.sleep(1)
        return result

    def stop_running_campaign(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        """
        Stop a campaign by name.
        If the timeout is reached and the campaign is not properly stopped yet, it will raise an TimeoutError.
        """

        timeout_handler = TimeoutHandler(timeout, "Campaign did not stop in the expected timeout")
        try:
            post(
                f"{self.url_base}/tmas/{self.TMA_NUMBER}/campaigns/actions/stop",
                timeout=timeout_handler.get_remaining_timeout(),
            )
        except TimeoutError as exc:
            raise RuntimeError("Viavi API call timed out while waiting for campaign to stop") from exc

        self.wait_until_running_campaign_finishes(timeout=timeout_handler.get_remaining_timeout())

    # pylint: disable=too-many-return-statements
    def get_running_campaign_info(self, *args, **kwargs) -> CampaignInfo:
        """
        Get the campaign status
        @returns Campaign Status
        """

        response = get(f"{self.url_base}/tmas/{self.TMA_NUMBER}/campaigns/actions/run", *args, **kwargs)

        if CampaignStatusEnum.NOTHING.value in response:
            return CampaignInfo(status=CampaignStatusEnum.NOTHING)

        if CampaignStatusEnum.WAITING.value in response:
            return CampaignInfo(status=CampaignStatusEnum.WAITING)

        if CampaignStatusEnum.RUNNING.value in response:
            # Running
            result = re.search(self._CAMPAIGN_RUNNING_REGEX, response)
            if result:
                return CampaignInfo(
                    status=CampaignStatusEnum.RUNNING, test_name=result.group(2), progress=int(result.group(4))
                )

            # Test passed
            result = re.search(self._TEST_PASSED_REGEX, response)
            if result:
                return CampaignInfo(status=CampaignStatusEnum.RUNNING, test_name=result.group(1), progress=100)

            # Test failed
            result = re.search(self._TEST_FAILED_REGEX, response)
            if result:
                return CampaignInfo(status=CampaignStatusEnum.RUNNING, test_name=result.group(1), progress=100)

            # Campaign passed
            result = re.search(self._CAMPAIGN_PASSED_REGEX, response)
            if result:
                return CampaignInfo(status=CampaignStatusEnum.PASS, progress=100)

            # Campaign failed
            result = re.search(self._CAMPAIGN_FAILED_REGEX, response)
            if result:
                return CampaignInfo(status=CampaignStatusEnum.FAIL, message=result.group(3), progress=100)

        return CampaignInfo()

    def _get_running_campaign_info_context(self, timeout: float = -1) -> Generator[CampaignInfo, None, None]:
        info = CampaignInfo()
        last_campaign = CampaignInfo()

        timeout_handler = TimeoutHandler(timeout, "Campaign did not finish in the expected timeout")
        while timeout_handler.not_reached():
            info = self.get_running_campaign_info(timeout_handler.get_remaining_timeout())
            if last_campaign != info:
                logging.info("%s [%s%%] %s", info.status, str(info.progress).rjust(3), info.message)
            yield info

            if info.status in (
                CampaignStatusEnum.NOTHING,
                CampaignStatusEnum.PASS,
                CampaignStatusEnum.FAIL,
            ):
                break

            last_campaign = info
            time.sleep(1)

    def wait_until_running_campaign_finishes(self, timeout: float = -1) -> CampaignInfo:
        """
        Wait until the current campaign finishes and return its status
        """

        info = CampaignInfo()
        for info in self._get_running_campaign_info_context(timeout=timeout):
            pass
        return info

    def wait_until_running_campaign_teardown(self, timeout: float = -1) -> CampaignInfo:
        """
        Wait until the current campaign starts the teardown and return last status
        """

        info = CampaignInfo()
        last_campaign = CampaignInfo()
        running_time = 0

        for info in self._get_running_campaign_info_context(timeout=timeout):
            if info.status is CampaignStatusEnum.RUNNING and info.progress >= 80:
                if last_campaign.progress == info.progress:
                    running_time += 1
                elif info.progress > last_campaign.progress:
                    if running_time > 60:
                        break
                    running_time = 0
            last_campaign = info
        return info

    ############################################################################
    # Reports
    ############################################################################
    def generate_report(self, campaign_name, timeout: float = _REPORT_TIMEOUT) -> str:
        """
        Generate a report
        @returns Remote Folder
        """
        timeout_handler = TimeoutHandler(timeout, "Reports couldn't be generated in the specified timeout")

        url = f"{self.url_base}/tmas/{self.TMA_NUMBER}/campaigns/actions/generatereport"
        while timeout_handler.not_reached():
            try:
                post(
                    url,
                    {
                        "CAMPAIGN_NAME": campaign_name,
                    },
                    timeout=timeout_handler.get_remaining_timeout(),
                )
                break
            except HTTPError:
                time.sleep(1)
            except TimeoutError as exc:
                raise RuntimeError("Viavi API call timed out while waiting for report to be generated") from exc

        while timeout_handler.not_reached():
            try:
                _, report_folder, status, *_ = get(url, timeout=timeout_handler.get_remaining_timeout()).split('" ')
                if status == "PASS":
                    report_folder = report_folder.replace('"', "")
                    break
            except (HTTPError, ValueError):
                pass
            time.sleep(1)

        return report_folder

    def download_directory(self, remote_folder: str, local_folder: str):
        super().download_directory(remote_folder, local_folder)
        super().remove_directory(remote_folder)

        for path, _, files in os.walk(local_folder):
            for name in files:
                if "Command_Log000" in name:
                    try:
                        log_filename = os.path.join(path, name)
                        procedure_table = parse_procedure_table(log_filename)
                        if procedure_table:
                            dl_ul_dict = parse_dl_ul_metrics(log_filename)
                            create_procedure_html_report(
                                procedure_table, os.path.join(os.path.dirname(log_filename), "viavi_report.html")
                            )
                            self._kpis = ViaviKPIs(
                                failures=[
                                    ViaviProcedureFailure(
                                        procedure_group=pg, procedure_name=pn, nof_failure=pn["failure"]
                                    )
                                    for pg, pn in procedure_table.items()
                                    if pn != "header"
                                    if "failure" in pn and isinstance(pn["failure"], int) and pn["failure"] > 0
                                ],
                                dl_data=_create_viavi_link_data(dl_ul_dict.get(KOS_HEADERS[0], {})),
                                ul_data=_create_viavi_link_data(dl_ul_dict.get(KOS_HEADERS[1], {})),
                                warning_array=parse_warnings(log_filename),
                            )
                            return
                    except Exception as err:  # pylint: disable=broad-except
                        logging.exception(err)
            logging.error("Procedure Table and DL/UL metrics not found in test report %s", local_folder)

    def get_test_kpis(self) -> ViaviKPIs:
        """
        Get test failures
        """
        return self._kpis


def _create_viavi_link_data(data_dict: Dict) -> ViaviLinkData:
    return ViaviLinkData(
        ber=data_dict.get("BER", 0),
        bler=data_dict.get("BLER", 0),
        num_tbs=data_dict.get("NumTBs", 0),
        num_tbs_errors=data_dict.get("NumTBErrors", 0),
        num_tbs_ack=data_dict.get("NumTBsAck", 0),
        num_tbs_nack=data_dict.get("NumTBsNack", 0),
        num_tbs_newly_transmitted=data_dict.get("NumTBsNewlyTransmitted", 0),
        num_tbs_repeated=data_dict.get("NumTBsRepeated", 0),
        num_tbs_retransmitted=data_dict.get("NumTBsRetransmitted", 0),
        num_bits=data_dict.get("NumBits", 0),
        num_bits_ack=data_dict.get("NumBitsAck", 0),
        total_bits=data_dict.get("Total Bits", 0),
        total_bits_errors=data_dict.get("Total Bit Errors", 0),
    )


class TimeoutHandler:
    """
    Checks if a timeout has been reached and related logic
    """

    def __init__(self, timeout: float = -1, msg: str = "Timeout reached") -> None:
        """
        If timeout <= 0, it will wait forever
        """
        self._time_to_reach = None if timeout <= 0 else time.time() + timeout
        self._msg = msg

    def not_reached(self) -> bool:
        """
        It will return true if the timeout has not been reached.
        If not, It will raise a TimeoutError
        """
        if self._time_to_reach is not None and time.time() >= self._time_to_reach:
            raise TimeoutError(self._msg)
        return True

    def get_remaining_timeout(self) -> float:
        """
        It will return the remaining timeout, if >0
        If original timeout has been reached, It will raise a TimeoutError
        If the original timeout was <=0, it will return -1
        """
        if self._time_to_reach is None:
            return -1  # Special value for no wait
        remaining_timeout = self._time_to_reach - time.time()
        if remaining_timeout <= 0:
            raise TimeoutError(self._msg)
        return remaining_timeout
