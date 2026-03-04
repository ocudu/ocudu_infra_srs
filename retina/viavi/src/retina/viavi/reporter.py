# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Viavi reporter
"""

import os
import re
from contextlib import suppress
from enum import Enum
from typing import Any, Dict, Generator, List

PROCEDURE_TABLE_DECLARATION = [
    # {
    #     "name": "",
    #     "header": ["procedure", "count", "success", "failure", "timeout"],
    #     "last_column": "UE_CONTEXT_RELEASE_(CU-INIT)",
    # },
    {
        "name": "RRC_PROCEDURE",
        "header": ["procedure", "count", "success", "failure", "mean time", "max time", "min time"],
        "last_column": "NR_CONDITIONAL_HANDOVER_ON_FAILURE",
    },
    {
        "name": "EMM_PROCEDURE",
        "header": ["procedure", "count", "retry", "success", "failure", "mean time"],
        "last_column": "SMS_MT",
    },
    {
        "name": "ESM_PROCEDURE",
        "header": ["procedure", "count", "retry", "success", "failure", "mean time"],
        "last_column": "DATA_TRANSPORT",
    },
    {
        "name": "NMM_PROCEDURE",
        "header": ["procedure", "count", "retry", "success", "failure", "mean time"],
        "last_column": "SMS_MT",
    },
    {
        "name": "NSM_PROCEDURE",
        "header": ["procedure", "count", "retry", "success", "failure", "mean time"],
        "last_column": "AUTHENTICATION",
    },
]


KOS_HEADERS = ("DL-SCH", "UL-SCH")


class _State(Enum):
    """
    State
    """

    SEARCHING_HEADER = 1
    READING_ROW = 2


def parse_procedure_table(log_file: str) -> Dict:
    """
    Parse log looking for procedure tables
    """
    return _parse_tables_in_log(log_file, PROCEDURE_TABLE_DECLARATION)


def _parse_log(log_file: str) -> Generator[str, None, None]:
    with open(log_file, "r", encoding="utf-8") as file:
        log = file.read()
    log_line_list = log.split("\n")
    log_line_no_date_list = [re.sub(r"\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}:\d{3} ", "", line) for line in log_line_list]
    yield from log_line_no_date_list


# pylint: disable=too-many-locals
def _parse_tables_in_log(log_file: str, table_list: List[Dict]) -> Dict:
    state = _State.SEARCHING_HEADER

    table_counter = 0
    table_to_search = table_list[0]

    result = {}
    row_list: Dict = {}

    for line in _parse_log(log_file):
        if state == _State.SEARCHING_HEADER:
            header_list = [element.lower() for element in table_to_search["header"]]
            fields = re.split(r"\[", line)
            fields_cleaned = [field.replace("]", "").strip().lower() for field in fields]
            fields_cleaned = [element for element in fields_cleaned if element != ""]
            if all(element in fields_cleaned for element in header_list):
                state = _State.READING_ROW
                row_list = {
                    "header": table_to_search["header"][1:],
                }
            continue

        if state == _State.READING_ROW:
            element_list = re.split(r"\s{3,}", line)
            row = {}
            for idx, header_inst in enumerate(table_to_search["header"]):
                if idx == 0:
                    continue
                try:
                    row[header_inst.lower()] = _convert_data_from_log(element_list[idx])
                # pylint: disable=bare-except
                except:
                    row[header_inst.lower()] = None
            row_list[element_list[0].lower()] = row

            if element_list[0] == table_to_search["last_column"]:
                state = _State.SEARCHING_HEADER
                result[table_to_search["name"]] = row_list
                table_counter += 1
                if table_counter == len(table_list):
                    break
                table_to_search = table_list[table_counter]
                continue
    return result


def _convert_data_from_log(data: str):
    """
    Convert data from log to the appropriate type.
    """
    data = data.strip()
    if data == "-" or not data:
        return None
    try:
        return int(data)
    except ValueError:
        try:
            return float(data)
        except ValueError:
            return None


def create_procedure_html_report(procedure_dict: Dict, output_path: str) -> None:
    """
    Get HTML report
    """
    with suppress(Exception):
        html_str = ""
        for key in procedure_dict:
            if key != "":
                html_str += f'<div class="alert alert-primary" role="alert"><h2>{key}</h2></div>\n'
                html_str += '<table class="table table-striped">\n'
                for row_key in procedure_dict[key]:
                    html_str += "  <tr>\n"

                    element_tag = "th" if row_key == "header" else "td"

                    if row_key != "header":
                        html_str += f"    <{element_tag}>{row_key}</{element_tag}>\n"
                    else:
                        html_str += f"    <{element_tag}>procedure</{element_tag}>\n"

                    for column_key in procedure_dict[key][row_key]:
                        if row_key == "header":
                            html_str += f"    <{element_tag}>{column_key}</{element_tag}>\n"
                        else:
                            html_str += (
                                f"    <{element_tag}>{procedure_dict[key][row_key][column_key]}</{element_tag}>\n"
                            )

                    html_str += "  </tr>\n"
            html_str += "</table>\n<br>\n"

        template_path = os.path.join(os.path.dirname(__file__), "report.html.nj")
        with open(template_path, "r", encoding="utf-8") as file:
            template = file.read()

        result = template.replace("mytable", html_str)

    if result:
        with open(output_path, mode="w", encoding="UTF-8") as file:
            file.write(result)


def parse_dl_ul_metrics(log_file: str) -> Dict:
    """
    Get DL and UL metrics from log
    """
    result: Dict[str, Dict[str, Any]] = {key: {} for key in KOS_HEADERS}

    current_block = None
    block_lines: Dict[str, List[str]] = {key: [] for key in KOS_HEADERS}

    for line in _parse_log(log_file):
        for key in KOS_HEADERS:
            if key in line:
                current_block = key
                block_lines[key] = []
                break
        if current_block is not None:
            block_lines[current_block].append(line)

    for key, lines in block_lines.items():
        iter_lines = iter(lines)
        while True:
            try:
                headers_line = next(iter_lines)
                if "[" in headers_line:
                    headers = re.findall(r"\[([^\]]+)\]", headers_line)
                    values_line = next(iter_lines)
                    values = map(_convert_data_from_log, re.split(r"\s+", values_line.strip()))
                    result[key] = dict(zip(headers, values))
                    break
            except StopIteration:
                break
    return result


def parse_warnings(log_file: str) -> List[str]:
    """
    Get warnings from log
    """
    result = []
    for line in _parse_log(log_file):
        if " WARN:" in line:
            result.append(line.strip())
    return result
