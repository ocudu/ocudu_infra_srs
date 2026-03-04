# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Collection of functions for working with exit codes.
"""


def exit_code_to_message(exit_code: int):
    """
    Convert an exit code to a human-readable message.

    Args:
        exit_code (int): The exit code to convert.

    Returns:
        str: A message corresponding to the exit code. If the exit code is not recognized,
             "Unknown exit code" is returned.
    """
    if exit_code is None:
        return "Running"
    messages = {
        0: "Success",
        1: "General error",
        2: "Misuse of shell builtins",
        4: "Illegal instruction",
        5: "Trace/breakpoint trap",
        6: "Abnormal termination",
        8: "Erroneous arithmetic operation",
        9: "Killed",
        11: "Segfault",
        13: "Broken pipe",
        14: "Alarm clock",
        15: "Termination request",
        126: "Command invoked cannot execute",
        127: "Command not found",
        128: "Invalid exit argument",
        130: "Script terminated by Control-C",
        255: "Exit status out of range",
    }
    return messages.get(abs(exit_code), "Unknown exit code")
