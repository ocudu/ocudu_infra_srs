# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Use & customize python logging standard library
"""

import logging
from logging import LogRecord

from retina.protocol.redact import setup_secret_log_filter

from retina.agent.tools.string import remove_ansi_escapes

FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


class ColorConsoleFormatter(logging.Formatter):
    """
    Formatter that prints messages in a color according to the severity level
    """

    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLDER_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: "%(message)s",
        logging.INFO: GREEN + FORMAT + RESET,
        logging.WARNING: YELLOW + FORMAT + RESET,
        logging.ERROR: RED + FORMAT + RESET,
        logging.CRITICAL: BOLDER_RED + FORMAT + RESET,
    }

    def format(self, record: LogRecord):
        return logging.Formatter(self.FORMATS.get(record.levelno, FORMAT)).format(record)


class FileFormatter(logging.Formatter):
    """
    Formatter that clean ansi escape syntax
    """

    def format(self, record: LogRecord):
        return remove_ansi_escapes(logging.Formatter(FORMAT).format(record))


def _clean_up_logging():
    for log_handler in logging.root.handlers:
        logging.root.removeHandler(log_handler)


def _add_color_console_handler():
    handler = logging.StreamHandler()
    handler.setFormatter(ColorConsoleFormatter())
    logging.root.addHandler(handler)


def _add_file_handler(filename: str):
    handler = logging.FileHandler(filename)
    handler.setFormatter(FileFormatter())
    logging.root.addHandler(handler)


def _set_level():
    logging.root.setLevel(logging.DEBUG)


def retina_log_setup(filename: str):
    """
    Set-up python logging library with customized options for retina
    (levels, format, color, etc.)
    """
    _clean_up_logging()
    setup_secret_log_filter()
    _add_color_console_handler()
    _add_file_handler(filename)
    _set_level()
