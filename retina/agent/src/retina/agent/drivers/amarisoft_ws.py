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
from threading import Lock, Thread
from time import sleep
from typing import Any, Callable, Dict, NamedTuple, Optional

import websocket

from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.parameters import testbed_defaults
from retina.agent.tools.threading import join_thread
from retina.agent.tools.time import TimeoutHandler


class _EventHandler(NamedTuple):
    matcher: Callable[[Dict], bool]
    key_fn: Callable[[Dict], Any]


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

        # Async/unsolicited event counters, populated as they arrive on the
        # socket rather than in response to a specific request. Distinct from
        # _queue_dict: an event's own "message_id" is a domain value (e.g. the
        # 3GPP PWS Message Identifier), not a request-correlation ID, so it
        # must never be routed through the message_id-keyed reply queues.
        # Events aren't self-identifying (unlike command replies, which echo
        # the command name as a string in "message", an event's own "message"
        # field holds its payload instead - e.g. pws_msg's is the decoded
        # warning-text array) so each registered event needs its own matcher
        # predicate to recognize its shape. Counts are further broken down by
        # a caller-supplied key (e.g. (ue_id, message_id)) so callers can
        # attribute occurrences to a specific UE/message rather than only a
        # global total.
        self._event_counts: Dict[str, Dict[Any, int]] = {}
        self._event_handlers: Dict[str, _EventHandler] = {}
        self._event_lock = Lock()

        # Parse Startup message
        response = self._read_message()
        if response.get("message", "") != "ready":
            raise ConnectionError("Websocket connection to Amarisoft couldn't be established.")

        self._read_thread = Thread(target=self._read)
        self._read_thread.start()

    def register_event(self, event_name: str, matcher: Callable[[Dict], bool], key_fn: Callable[[Dict], Any]) -> None:
        """
        Subscribe to an async/unsolicited event type (e.g. "pws_msg") and start
        counting its occurrences, retrievable via event_count()/event_counts().
        `matcher` decides whether an incoming message is an instance of this
        event - events don't carry a self-identifying type tag, so this must
        be based on the event's own distinctive shape (see the pws_msg example
        caller). `key_fn` extracts a hashable key (e.g. (ue_id, message_id))
        from a matched message, so occurrences can be attributed rather than
        only totalled.
        """
        with self._event_lock:
            self._event_counts.setdefault(event_name, {})
            self._event_handlers[event_name] = _EventHandler(matcher, key_fn)
        self.send_command_and_wait_response(message="register", register=event_name)

    def event_count(self, event_name: str, key: Any = None) -> int:
        """
        Return how many times a registered event has been received. With
        `key` (as produced by that event's key_fn), return the count for that
        key only; otherwise the total across all keys.
        """
        with self._event_lock:
            counts = self._event_counts.get(event_name, {})
            return counts.get(key, 0) if key is not None else sum(counts.values())

    def event_counts(self, event_name: str) -> Dict[Any, int]:
        """Return a copy of the per-key counts for a registered event."""
        with self._event_lock:
            return dict(self._event_counts.get(event_name, {}))

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
                if not msg:
                    continue
                if self._count_if_event(msg):
                    continue
                with suppress(KeyError):
                    # Send msg to waiting queue, if exists
                    self._queue_dict[int(msg["message_id"])].put(msg)

    def _count_if_event(self, msg: Dict) -> bool:
        """If msg matches a registered async event, tally it and return True."""
        with self._event_lock:
            for event_name, handler in self._event_handlers.items():
                if handler.matcher(msg):
                    key = handler.key_fn(msg)
                    counts = self._event_counts[event_name]
                    counts[key] = counts.get(key, 0) + 1
                    return True
            return False

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

    @property
    def connected(self) -> bool:
        """
        True while the socket can still carry commands. Closing it (quit/close) doesn't
        clear the driver's reference, so checking for `not None` alone isn't enough.
        """
        return bool(self._ws.connected)

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
