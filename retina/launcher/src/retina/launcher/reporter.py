# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Reporter
"""

import contextlib
import json
import os
import pathlib
from pprint import pformat
from typing import Any, Dict, List

import jinja2
from retina.protocol.redact import redact_string

_IGNORE_EXTENSIONS_TO_HTML = (".pcap", ".dat", ".idx")
_MAX_FILE_SIZE_TO_HTML = 10 * 1024 * 1024
_EXCLUDE_FILE_LIST = (
    "1m.csv",
    "2s.csv",
    "TMA_Stats.html",
    "additional_logs.csv",
    "Default User",
    "SessionHistory",
    "FTL.dat",
)
REPORT_FILENAME = "test.html"


def create_report(
    test_log_folder: str, report_html_path: str, test_config: Dict, test_name: str, testbed_info: Dict
) -> str:
    """
    Create report
    """

    with open(pathlib.Path(test_log_folder) / "testbed.json", "w", encoding="UTF-8") as testbed_f:
        testbed_f.write(redact_string(pformat(testbed_info, indent=4)))

    bin_folders = []
    with contextlib.suppress(Exception):
        bin_folders = os.listdir(test_log_folder)
    bin_list: List[Dict[str, Any]] = []
    for f_bin in bin_folders:
        f_path = f"{test_log_folder}/{f_bin}"
        if os.path.isdir(f_path):
            with contextlib.suppress(Exception):
                output_list: List[Dict[str, str]] = []
                for path, _, files in os.walk(f_path):
                    for name in files:
                        _, file_extension = os.path.splitext(os.path.join(path, name))
                        if not any(excluded in name for excluded in _EXCLUDE_FILE_LIST):
                            add_to_report(file_extension, output_list, os.path.join(path, name), test_log_folder)

                bin_list.append({"name": f_bin, "output": sorted(output_list, key=lambda x: x["name"])})  # type: ignore

    bin_list = sorted(bin_list, key=lambda x: x["name"])
    return write_html_report(test_log_folder, report_html_path, bin_list, test_config, test_name)


def format_file_size(file_size_bytes: int):
    """
    Format file size
    """
    file_size_kb = file_size_bytes / 1024
    file_size_mb = file_size_kb / 1024

    if file_size_bytes < 1024:
        return f"{file_size_bytes} bytes"
    if file_size_bytes < 1024 * 1024:
        return f"{file_size_kb:.2f} KB"
    if file_size_mb >= 1024:
        file_size_gb = file_size_mb / 1024
        return f"{file_size_gb:.2f} GB"
    return f"{file_size_mb:.2f} MB"


def add_to_report(file_extension: str, output_list: List[Dict[str, str]], current_out_path: str, output_folder: str):
    """
    Add to report
    """
    name = os.path.basename(current_out_path)
    simple_name = name
    path = os.path.relpath(current_out_path, output_folder)
    path_complete = path

    file_size = os.path.getsize(current_out_path)
    if file_extension == ".html":
        name += " | Online View"
    else:
        if file_extension in _IGNORE_EXTENSIONS_TO_HTML:
            pass
        elif file_size < _MAX_FILE_SIZE_TO_HTML:
            name += " | Online View"
            path += ".html"
            transform_to_html(current_out_path)
        else:
            name += " (too big for online view)"

    name += f" [{format_file_size(file_size)}]"

    output_list.append(
        {
            "name": name,
            "simple_name": simple_name,
            "path": path,
            "path_complete": path_complete,
        }
    )


def write_html_report(
    test_log_folder: str, report_html_path: str, bin_list: List[Dict], test_config: Dict, test_name: str
) -> str:
    """
    Write final html
    """

    path_to_main_html = os.path.relpath(report_html_path, start=test_log_folder)
    testbed = []

    with contextlib.suppress(FileNotFoundError, json.JSONDecodeError):
        with open(os.path.join(test_log_folder, "testbed.json"), "r", encoding="UTF-8") as testbed_f:
            testbed = testbed_f.readlines()

    template_path = os.path.join(os.path.dirname(__file__), "index.html.nj")
    with open(template_path, encoding="UTF-8", mode="r") as file:
        template_str = file.read()
        template = jinja2.Template(template_str).render(
            output_list=bin_list,
            test_config=test_config,
            test_name=test_name,
            str_config=json.dumps(test_config, indent=4),
            str_testbed=json.dumps(testbed, indent=4),
            path_to_main_html=path_to_main_html,
        )

    output_path = f"{test_log_folder}/{REPORT_FILENAME}"
    if not pathlib.Path(test_log_folder).exists():
        os.mkdir(test_log_folder)

    with open(output_path, mode="w", encoding="UTF-8") as file:
        file.write(redact_string(template))
    return "./" + os.path.normpath(os.path.relpath(output_path, start=os.path.join(report_html_path, "..")))


def transform_to_html(input_path: str):
    """
    Log to HTML
    """
    lang = "plaintext"
    _, file_extension = os.path.splitext(input_path)
    if file_extension in (".yml", ".yaml"):
        lang = "yaml"
    elif file_extension in (".cfg", ".json"):
        lang = "json"

    with open(input_path, mode="r", encoding="UTF-8") as file:
        content = file.read()

    content = replace_colors(content)

    template_path = os.path.join(os.path.dirname(__file__), "log.html.nj")
    with open(template_path, encoding="UTF-8") as file:
        template_str = file.read()
        template = jinja2.Template(template_str).render(content=content, lang=lang)

    output_path = input_path + ".html"
    with open(output_path, mode="w", encoding="UTF-8") as file:
        file.write(template)


WARNING_COLOR = "#d39d00"
INFO_COLOR = "green"
ERROR_COLOR = "red"
DEBUG_COLOR = "blue"


def replace_colors(content: str) -> str:
    """
    Set log colors
    """

    keywords = [
        {"key": "INFO:", "color": INFO_COLOR},
        {"key": "WARNING:", "color": WARNING_COLOR},
        {"key": "ERROR:", "color": ERROR_COLOR},
        {"key": "[INFO]", "color": INFO_COLOR},
        {"key": "[WARNING]", "color": WARNING_COLOR},
        {"key": "[ERROR]", "color": ERROR_COLOR},
        {"key": "[I]", "color": INFO_COLOR},
        {"key": "[W]", "color": WARNING_COLOR},
        {"key": "[E]", "color": ERROR_COLOR},
        {"key": "- INFO -", "color": INFO_COLOR},
        {"key": "- WARNING -", "color": WARNING_COLOR},
        {"key": "- ERROR -", "color": ERROR_COLOR},
        {"key": "- DEBUG -", "color": DEBUG_COLOR},
        {"key": "Traceback", "color": ERROR_COLOR},
    ]
    for keyword_inst in keywords:
        content = content.replace(
            keyword_inst["key"],
            f'<b><p style="color:{keyword_inst["color"]};display:inline">{keyword_inst["key"]}</p></b>',
        )
    return content
