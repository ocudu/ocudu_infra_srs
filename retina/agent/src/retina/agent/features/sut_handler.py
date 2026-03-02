#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Agent logic in charge of managing a software under test
"""

import logging
import os
import platform
import re
from abc import ABCMeta
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from time import sleep
from typing import Generator, Iterable, List, Optional, TextIO, Tuple

import grpc
import psutil
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import Metrics, StopResponse
from retina.protocol.exit_codes import exit_code_to_message

from retina.agent.drivers.base import BaseDriver
from retina.agent.features.executor import LocalExecutor
from retina.agent.tools.cgroups import log_cgroups_warnings_and_errors
from retina.agent.tools.string import remove_ansi_escapes
from retina.agent.tools.threading import join_thread
from retina.agent.tools.time import TimeoutHandler


@dataclass
class StopInfo:
    """
    Stop related info
    """

    exit_code: int = 0
    error_count: int = 0
    error_msg: str = ""
    warning_count: int = 0
    warning_msg: str = ""


# pylint: disable=too-many-instance-attributes
class BaseDriverSutHandler(BaseDriver, metaclass=ABCMeta):
    """
    Manage a Software Under Tests
    """

    _CHECK_ALIVE_STEP: float = 1
    _READ_FROM_FILE_STEP: float = 0.1

    def __init__(self, *args, **kwargs) -> None:
        # Check alive and metrics measured in check alive thread
        self._check_alive_thread = Thread(target=self._check_alive)
        self._check_alive_event = Event()
        self._nof_lates: int = 0
        self._nof_under: int = 0
        self._nof_seq_err: int = 0
        # Process
        self._process: Optional[psutil.Process] = None
        # Logs
        self._last_log_array: Tuple[str, ...] = ()
        self._last_stop_result: StopInfo = StopInfo()
        self._logfile_descriptor: TextIO
        super().__init__(*args, **kwargs)

    @property
    def _expected_exit_code_array(self) -> Tuple[int, ...]:
        return (0,)

    @property
    def _is_alive(self) -> bool:
        """True if the process is still alive"""
        return bool(self._executor.is_process_alive(self._process))

    def start_sut(self, *cmd: str, logfile: str, dryrun: bool = False) -> None:
        """
        Start the sut using the given `cmd`
        :param cmd
        """

        self.stop_sut()

        # Filter empty items
        cmd = tuple(filter(lambda item: item.strip(), cmd))
        logging.info("CMD executed: %s", " ".join(cmd))
        if not dryrun:
            self._nof_lates = self._nof_under = self._nof_seq_err = 0
            self._start_binary(*cmd, logfile=logfile)

            self._check_alive_thread = Thread(target=self._check_alive)
            self._check_alive_event = Event()
            self._check_alive_thread.start()

    def stop_sut(self, stop_timeout: int = 0) -> StopInfo:
        """
        Stop the sut
        """
        self._check_alive_event.set()
        join_thread(self._check_alive_thread)
        return self._stop_binary(stop_timeout)

    def _start_binary(self, *cmd: str, logfile: str) -> None:
        """
        Start the process local or remotely
        :param cmd
        """
        self._logfile_descriptor = open(logfile, "w", encoding="utf-8")  # pylint: disable=consider-using-with
        self._process = self._executor.create_process(*cmd, logfile=self._logfile_descriptor)

    def _check_alive(self) -> None:
        """
        Thread that periodically checks if the sut is still alive.
        It not, it'll warm using the log and stop this thread.
        """
        while not self._check_alive_event.is_set():
            if self._process is not None and not self._is_alive:
                logging.warning("Process has died with return code %d", self._process.returncode)
                self._check_alive_event.set()
            else:
                self._write_ps_info()
                self._check_alive_event.wait(self._CHECK_ALIVE_STEP)
            self._logfile_descriptor.flush()

    def _write_ps_info(self):
        if self._process is not None and platform.system().lower() == "linux":
            with Path(self.get_filepath_in_report_folder(f"ps_info_{self._process.name()}.txt")).open(
                mode="a", encoding="utf-8"
            ) as fd:
                for line in self._executor.run_binary("date"):
                    fd.write(line + os.linesep)
                for line in self._executor.run_binary(
                    "ps",
                    "-Lo",
                    "pid,tid,class,rtprio,pcpu,rss,vsz,comm",
                    "--pid",
                    str(self._process.pid),
                    raise_if_exit_code=False,
                ):
                    fd.write(line + os.linesep)
                fd.write(os.linesep)

    def Stop(self, request: UInt32Value, context: Optional[grpc.ServicerContext]) -> StopResponse:
        stop_info = self.stop_sut(request.value)
        super().Stop(request, context)
        return StopResponse(
            exit_code=stop_info.exit_code,
            error_count=stop_info.error_count,
            error_msg=stop_info.error_msg,
            warning_count=stop_info.warning_count,
            warning_msg=stop_info.warning_msg,
        )

    @property
    def _warning_regex(self) -> str:
        return ""

    @property
    def _error_regex(self) -> str:
        return ""

    @property
    def _exit_children_first(self) -> bool:
        return False

    def _stop_binary(self, stop_timeout: int = 0) -> StopInfo:
        """
        Stop the process
        """
        if not stop_timeout:
            stop_timeout = LocalExecutor.EXIT_PROCESS_TIMEOUT

        if self._process is not None:
            child_failed = False
            # End child process and save if a child process has exit code != 0
            if self._exit_children_first and self._process.is_running():
                for child_process in self._process.children():
                    child_failed |= int(self._executor.exit_process(child_process, timeout=stop_timeout)) != 0

            # End process
            return_code = int(self._executor.exit_process(self._process, timeout=stop_timeout))
            self._process = None
            self._logfile_descriptor.flush()
            self._logfile_descriptor.close()
            logging.info("sut stopped with return code %d (%s)", return_code, exit_code_to_message(return_code))

            # Tweak exit code
            if return_code in self._expected_exit_code_array:
                return_code = 0
            if not return_code and child_failed:
                return_code = -256
            self._last_stop_result.exit_code = return_code

            # Error and warning searching
            error_list = (
                self._re_search_files(
                    self._last_log_array,
                    self._error_regex,
                )
                if self._error_regex
                else []
            )
            self._last_stop_result.error_count = len(error_list)
            self._last_stop_result.error_msg = error_list[0] if error_list else ""

            if error_list:
                logging.warning("There are %s errors: \n%s", len(error_list), "\n".join(error_list))

            warning_list = (
                self._re_search_files(
                    self._last_log_array,
                    self._warning_regex,
                )
                if self._warning_regex
                else []
            )

            self._last_stop_result.warning_count = len(warning_list)
            self._last_stop_result.warning_msg = warning_list[0] if warning_list else ""

            if warning_list:
                logging.warning("There are %s warnings: \n%s", len(warning_list), "\n".join(warning_list))

            # Extract system metrics from log
            (
                self._nof_lates,
                self._nof_under,
                self._nof_seq_err,
            ) = _extract_uhd(self._last_log_array[0])

        return self._last_stop_result

    def read_from_log(
        self, regex_list: Tuple[str, ...], found_any: bool, timeout: Optional[int], from_beginning: bool = False
    ) -> List[Tuple[str, ...]]:
        """
        Reads from binary output until it matches any of the the specified regex's.

        :param regex_list:
        :return: List of Lists of str:
            -> One list for each regex requested
            -> Each regex list contains: full match and all groups match
            (if there is any in regex).
            Only the regex that matched first will have a non empty list
        """
        result: List[Tuple[str, ...]] = [()] * len(regex_list)

        pattern_list: Tuple = tuple(re.compile(regex, re.MULTILINE | re.DOTALL) for regex in regex_list)

        # pylint: disable=too-many-nested-blocks
        try:
            all_output = ""
            for data in self._get_log_line(timeout, from_beginning):
                all_output += data + os.linesep
                for index, value in enumerate(result):  # Iterate over result
                    if not value:  # If no result yet, we look for the match
                        msg_match = re.search(pattern_list[index], all_output)
                        if msg_match:
                            result[index] = (
                                msg_match.group(),
                                *(subitem for subitem in msg_match.groups()),
                            )
                            if found_any or (not found_any and () not in result):
                                return result
            return result
        except TimeoutError:
            raise TimeoutError(
                "Timeout reached while parsing the log looking for "
                + " | ".join(regex_list)
                + (
                    (os.linesep + "..." + os.linesep + os.linesep.join(all_output.splitlines()[-5:]))
                    if all_output
                    else ""
                )
            ) from None

    def _get_log_line(self, timeout: Optional[int], from_beginning: bool) -> Generator[str, None, None]:
        with open(self._last_log_array[0], "r", encoding="utf-8") as file_descriptor:
            for line in file_descriptor.readlines():
                if from_beginning:
                    yield remove_ansi_escapes(line)
            timeout_handler = TimeoutHandler(timeout)
            line = ""
            while timeout_handler.not_reached():
                if not self._check_alive_thread.is_alive():
                    raise ChildProcessError("Process is dead")
                line += file_descriptor.readline()
                if not line:
                    sleep(self._READ_FROM_FILE_STEP)
                elif line.endswith(os.linesep):
                    yield remove_ansi_escapes(line)
                    line = ""

    @staticmethod
    def _re_search_files(path_array: Iterable[str], regex: str) -> List[str]:
        """
        Search regex in an array of paths, processing files line by line, and stop if `stop_regex` is matched.
        """
        result_list = []
        for filepath in path_array:
            if Path(filepath).exists():
                with open(filepath, "r", encoding="utf-8") as file_descriptor:
                    with suppress(AttributeError):
                        for line in file_descriptor:
                            match = re.search(regex, line)
                            if match:
                                result_list.append(match.group())
        return result_list

    def GetMetrics(self, request: Empty, context: grpc.ServicerContext) -> Metrics:
        log_cgroups_warnings_and_errors()
        return Metrics(nof_lates=self._nof_lates, nof_under=self._nof_under, nof_seq_err=self._nof_seq_err)


#########
# Utils #
#########


def _extract_uhd(filepath: str) -> Tuple[int, int, int]:
    """
    Extract UHD error report from a file
    """
    text = ""
    with open(filepath, "r", encoding="UTF-8") as file:
        for line in file.readlines():
            text += line.rstrip() + os.linesep

    lates = under = seq_err = 0
    for result in (
        *re.findall(r"UHD status: L=(\d+) U=(\d+) S=(\d+)", text, flags=re.MULTILINE),
        *re.findall(r"Late: (\d+); Underflow: (\d+); Overflow: (\d+)", text, flags=re.MULTILINE),
    ):
        _lates, _under, _seq_err = result
        lates += int(_lates)
        under += int(_under)
        seq_err += int(_seq_err)
    return lates, under, seq_err
