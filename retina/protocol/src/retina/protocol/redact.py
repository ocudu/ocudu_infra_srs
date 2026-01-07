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


class _SecretFilter(logging.Filter):
    """
    Logging filter that redacts provided secret values from messages and args
    """

    def __init__(self, mask: str = "[masked]"):
        super().__init__()
        self._mask = mask
        self._secrets = set(secret for secret in os.getenv("RETINA_SECRETS", "").split(" ") if secret)

    def add_secret(self, secret: str) -> None:
        """Add secrets used for redaction."""
        self._secrets.add(secret)

    def _redact(self, value: str) -> str:
        """Return the input string with all secrets replaced by the mask."""
        for secret in self._secrets:
            value = value.replace(secret, self._mask)
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        """Apply redaction to the log record message and arguments."""
        if record.args:
            record.args = tuple(self._redact(arg) if isinstance(arg, str) else arg for arg in record.args)
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
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
