# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Amarisoft Websocket Utility
"""

import json
import logging
import queue
from abc import ABCMeta, abstractmethod
from contextlib import suppress
from pathlib import Path
from queue import Queue
from threading import Thread
from time import sleep
from typing import Dict, Optional

import websocket

from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.parameters import testbed_defaults
from retina.agent.tools.threading import join_thread
from retina.agent.tools.time import TimeoutHandler


class AmarisoftBaseDriver(BaseDriverSutHandler, metaclass=ABCMeta):
    """
    Amarisoft common logic for drivers
    """

    AMARISOFT_VERSION_REGEX: str = r"Core Network version (.*), Copyright"
    AMARISOFT_LICENSE_WAIT_BEFORE_RETRY: float = 2

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._websocket: Optional[AmarisoftWebSocket] = None

    @abstractmethod
    def _get_binary_name(self) -> str:
        pass

    def _get_amarisoft_folder(self) -> Path:
        return Path(self._executor.find_in_path(self._get_binary_name())).parent

    def _get_sut_version(self) -> str:
        output = tuple(
            self._executor.run_binary(
                self._get_binary_name(),
                "-h",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        version: str = self._parse_sut_version(output, self.AMARISOFT_VERSION_REGEX)
        return version

    def _get_log_variables(self, log_level: str, log_filename: str) -> Dict:
        # Log level conversion
        # Amarisoft doesn't have "info" mode and "warning" is called "warn"
        log_level = log_level.lower().strip()
        log_level = {"info": "debug", "warning": "error"}.get(log_level, log_level)
        return {
            "log_level": log_level,
            "log_filename": self.get_filepath_in_report_folder(log_filename),
        }

    def _is_license_available(self, timeout_handler: TimeoutHandler) -> bool:
        try:
            result = self.read_from_log(
                (
                    "Can't get license from server",
                    "Your license does not support",
                    "Your license is too old",
                    "Timeout while loading license floating",
                    "License error occurred",
                    "Server error",
                    "Support and software update available until",
                ),
                True,
                timeout=timeout_handler.get_remaining_timeout(),
                from_beginning=True,
            )

            if any(result[0:-1]):
                sleep(self.AMARISOFT_LICENSE_WAIT_BEFORE_RETRY)
                logging.warning("License in use. Let's try again")
                if timeout_handler.not_reached():
                    return False
            return True

        except TimeoutError:
            raise TimeoutError("Amarisoft License unavailable") from None

    def _kill_existing_lte(self) -> None:
        # Kill existing lte executions
        prev_lte_bin_array = tuple(
            self._executor.run_binary(
                "pkill",
                "-9",
                "--echo",
                "lte",
                keeplinebreaks=False,
                timeout=None,
                raise_if_exit_code=False,
            )
        )
        if prev_lte_bin_array:
            for prev_lte_bin in prev_lte_bin_array:
                logging.warning("Killing previous lte execution: %s", prev_lte_bin)
            sleep(self.AMARISOFT_LICENSE_WAIT_BEFORE_RETRY)


class AmarisoftWebSocket:
    """
    Websocket Utility
    """

    def __init__(self, timeout: Optional[int] = None) -> None:
        self._ws = websocket.create_connection(
            f"ws://{testbed_defaults.api_address}:{testbed_defaults.api_port}", timeout=timeout
        )
        self._queue_dict: Dict[int, Queue[Dict]] = {}
        self._msg_id_counter: int = 0

        # Parse Startup message
        response = self._read_message()
        if response.get("message", "") != "ready":
            raise ConnectionError("Websocket connection to Amarisoft couldn't be established.")

        self._read_thread = Thread(target=self._read)
        self._read_thread.start()

    def _send_command(self, **kwargs) -> int:
        """
        Send the command
        """
        # Get msg id from counter
        with self._ws.lock:
            self._msg_id_counter += 1
            message_id = self._msg_id_counter

        # Create queue
        if message_id not in self._queue_dict:
            self._queue_dict[message_id] = Queue[Dict]()

        # Send message with the generated message id
        msg_str = json.dumps({**kwargs, "message_id": str(message_id)})
        logging.debug("[ WS --> ] %s", msg_str)
        self._ws.send(msg_str)

        return message_id

    def _read_message(self) -> Dict:
        raw = self._ws.recv()
        try:
            msg: Dict = json.loads(raw)
        except json.JSONDecodeError:
            if raw:
                msg = {"raw": raw}
            else:
                msg = {}
                self.close()
        logging.debug("[ WS <-- ] %s", json.dumps(msg))
        return msg

    def _read(self) -> None:
        while self._ws.connected:
            with suppress(websocket.WebSocketConnectionClosedException, OSError):
                msg = self._read_message()
                if msg:
                    with suppress(KeyError):
                        # Send msg to waiting queue, if exists
                        self._queue_dict[int(msg["message_id"])].put(msg)

    def _wait_response_with_id(self, message_id: int, timeout: Optional[float] = None) -> Dict:
        """
        Wait `timeout` secs until a message with `msg_id` has been received.
        If the timeout is reached, it will raise a TimeoutError exception.
        """

        try:
            return self._queue_dict[message_id].get(timeout=timeout)
        # Not catching KeyError on purpose, so the user knows the ID doesn't exit
        except queue.Empty:
            raise TimeoutError from None

    def send_command_and_wait_response(self, response_timeout: float = 30, **kwargs) -> Dict:
        """
        Send a command and wait until its response
        """
        if kwargs.get("timeout", None) is not None and response_timeout < kwargs["timeout"]:
            response_timeout = kwargs["timeout"] + 1
        if self._ws.connected:
            return self._wait_response_with_id(self._send_command(**kwargs), timeout=response_timeout)
        logging.warning("WS already closed")
        return {}

    def quit(self) -> None:
        """
        Send quit command and close the websocket. Returns the stats response dict.
        """
        if self._ws.connected:
            with suppress(websocket.WebSocketConnectionClosedException):
                logging.info("Sending quit command")
                self.send_command_and_wait_response(message="quit")
                self.close()
        else:
            logging.info("Websocket connection already closed")

    def close(self) -> None:
        """
        Close websocket connection
        """
        with suppress(TimeoutError, websocket.WebSocketConnectionClosedException):
            self._ws.close()
        join_thread(self._read_thread)
