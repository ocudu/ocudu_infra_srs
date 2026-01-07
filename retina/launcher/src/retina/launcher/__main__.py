#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Pytest wrapper
"""

import shlex
import signal
import sys

import pytest
from retina.protocol.redact import setup_secret_log_filter


def _signal_handler(*args, **kwargs):
    raise KeyboardInterrupt


def main():
    """
    Entry point
    """
    setup_secret_log_filter()
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGTSTP, _signal_handler)
    signal.signal(signal.SIGQUIT, _signal_handler)
    sys.exit(pytest.main(shlex.split(" ".join(f'"{arg}"' for arg in sys.argv[1:]), posix=True)))


if __name__ == "__main__":
    main()
