#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
RestClient Basic Logic
"""

import json
from typing import Any, Dict, Optional

import requests

HEADERS: Dict[str, str] = {"Content-Type": "application/json"}
DEFAULT_TIMEOUT: int = 60


def get(url: str, timeout: Optional[float] = DEFAULT_TIMEOUT, **kwargs) -> str:
    """
    Send a GET request to the given URL
    Raise HTTPError if response's status code is not ok
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=_convert_timeout(timeout), **kwargs)
        _raise_for_status(response)
        return response.text.lstrip()
    except requests.ReadTimeout as err:
        raise TimeoutError from err


def post(url: str, data: Optional[Dict[str, Any]] = None, timeout: Optional[float] = DEFAULT_TIMEOUT, **kwargs) -> str:
    """
    Send a POST request to the given URL with the given data
    Raise HTTPError if response's status code is not ok
    """
    try:
        data_string = ""
        if data:
            data_string = json.dumps(data)
        response = requests.post(url, data=data_string, headers=HEADERS, timeout=_convert_timeout(timeout), **kwargs)
        _raise_for_status(response)
        return response.text.lstrip()
    except requests.ReadTimeout as err:
        raise TimeoutError from err


def delete(url: str, timeout: Optional[float] = DEFAULT_TIMEOUT, **kwargs) -> None:
    """
    Send a DELETE request to the given URL
    Raise HTTPError if response's status code is not ok
    """
    try:
        response = requests.delete(url, headers=HEADERS, timeout=_convert_timeout(timeout), **kwargs)
        _raise_for_status(response)
    except requests.ReadTimeout as err:
        raise TimeoutError from err


def _convert_timeout(timeout: Optional[float]) -> float:
    return DEFAULT_TIMEOUT if (timeout is None or timeout <= 0) else timeout


def _raise_for_status(response: requests.Response):
    """Raises :class:`HTTPError`, if one occurred."""

    http_error_msg = ""

    if isinstance(response.reason, bytes):
        # We attempt to decode utf-8 first because some servers
        # choose to localize their reason strings. If the string
        # isn't utf-8, we fall back to iso-8859-1 for all other
        # encodings. (See PR #3538)
        try:
            reason = response.reason.decode("utf-8")
        except UnicodeDecodeError:
            reason = response.reason.decode("iso-8859-1")
    else:
        reason = response.reason

    if 400 <= response.status_code < 500:
        http_error_msg = (
            f"{response.status_code} Client Error for url {response.url}: {reason} - {response.text.lstrip()}"
        )

    elif 500 <= response.status_code < 600:
        http_error_msg = (
            f"{response.status_code} Server Error for url {response.url}: {reason} - {response.text.lstrip()}"
        )

    if http_error_msg:
        raise requests.HTTPError(http_error_msg, response=response)
