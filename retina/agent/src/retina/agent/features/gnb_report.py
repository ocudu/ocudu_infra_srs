#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Reporter for GNB
"""

import datetime
import json
import os
from typing import Dict

import jinja2

METRICS_TO_PLOT = [
    {"name": "dl_nof_ok", "label": "DL nof OK", "scale": 1, "ylabel": "ok"},
    {"name": "ul_nof_ok", "label": "UL nof OK", "scale": 1, "ylabel": "ok"},
    {"name": "dl_nof_nok", "label": "DL nof NOK", "scale": 1, "ylabel": "nok"},
    {"name": "ul_nof_nok", "label": "UL nof NOK", "scale": 1, "ylabel": "nok"},
    {"name": "dl_brate", "label": "DL brate", "scale": 1e6, "ylabel": "Mbps"},
    {"name": "ul_brate", "label": "UL brate", "scale": 1e6, "ylabel": "Mbps"},
]


# pylint: disable=too-many-locals
def _get_metric(metric_array, metric_key, scale):
    """
    Get metric
    """
    ue_list_rnti = set()
    timestamp_list = []
    metric_then: Dict = {}
    for metric_data in metric_array:
        if "cells" in metric_data:
            timestamp = metric_data["timestamp"]

            metric_then[timestamp] = {}

            timestamp_list.append(timestamp)

            for cell in metric_data["cells"]:
                for ue_container in cell.get("ue_list", []):
                    rnti = ue_container["rnti"]
                    value = ue_container[metric_key]
                    metric_then[timestamp][rnti] = value / scale
                    ue_list_rnti.add(rnti)

    for sub_dict in metric_then.values():
        for rnti in ue_list_rnti:
            if rnti not in sub_dict:
                sub_dict[rnti] = 0

    data_list = []
    for index, rnti in enumerate(ue_list_rnti):
        data = {"label": rnti, "data": [], "hidden": str(index > 0).lower()}
        for sub_dict in metric_then.values():
            data["data"].append(sub_dict[rnti])
        data_list.append(data)
    return data_list, timestamp_list


def transform_metrics(metrics_path: str) -> None:
    """
    Transform metrics
    """
    if not metrics_path or not os.path.exists(metrics_path):
        return
    with open(metrics_path, "r", encoding="utf-8") as file:
        try:
            metrics = json.loads(file.read())
        except json.JSONDecodeError:
            return

    timestamp_list = []
    for metric in METRICS_TO_PLOT:
        data_list, timestamp_list = _get_metric(metrics, metric["name"], metric["scale"])
        metric["data_list"] = data_list

    timestamp_list = [
        datetime.datetime.fromisoformat(timestamp.strip()).strftime("%H:%M:%S") for timestamp in timestamp_list
    ]

    # Template
    template_path = os.path.join(os.path.dirname(__file__), "gnb_report.html.nj")
    with open(template_path, encoding="UTF-8", mode="r") as file:
        template_str = file.read()
        output = jinja2.Template(template_str).render(
            mylist=METRICS_TO_PLOT,
            timestamp_list=timestamp_list,
        )

    if output:
        output_path = os.path.join(os.path.dirname(metrics_path), "metrics.html")
        with open(output_path, mode="w", encoding="UTF-8") as file:
            file.write(output)
