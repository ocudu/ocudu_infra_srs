#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Helpers to redact sensitive values from log messages
"""

import logging
import os
import re
from typing import Optional, Set


class _SecretFilter(logging.Filter):
    """
    Logging filter that redacts provided secret values from messages and args
    """

    _REGEX_PATTERN = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5,7}[0-9A-Fa-f]{2}\b")
    _NOT_REDACT_ARRAY = ["srs", "ocudu", "retina", "ue", "gnb", "cu", "du", "ru", "core", "mme", "lte"]

    def __init__(self, mask: str = "[masked]"):
        super().__init__()
        self._mask = mask
        self._secrets: Set[str] = set()
        for secret in os.getenv("RETINA_SECRETS", "").split(" "):
            self.add_secret(secret)

    def add_secret(self, secret: Optional[str]) -> None:
        """Add secrets used for redaction."""
        if secret is None:
            return
        secret = secret.strip()
        if secret and secret not in self._NOT_REDACT_ARRAY:
            self._secrets.add(secret)

    def redact(self, value: Optional[str]) -> Optional[str]:
        """Return the input string with all secrets replaced by the mask."""
        if value is None:
            return value
        for secret in self._secrets:
            value = value.replace(secret, self._mask)
        value = self._REGEX_PATTERN.sub(self._mask, value)
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        """Apply redaction to the log record message and arguments."""
        if record.args:
            record.args = tuple(self.redact(arg) if isinstance(arg, str) else arg for arg in record.args)
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        return True


_SECRET_FILTER = _SecretFilter()


def add_log_secret(secret: str) -> None:
    """
    Add secret to be redacted from logs.
    """
    _SECRET_FILTER.add_secret(secret)


def setup_secret_log_filter() -> None:
    """
    Add the shared secret filter to the root logger.
    """
    logging.root.addFilter(_SECRET_FILTER)


def redact_string(value: Optional[str]) -> Optional[str]:
    """
    Redact secrets from a string using the shared secret filter.
    """
    return _SECRET_FILTER.redact(value)
