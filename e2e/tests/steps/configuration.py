# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Configuration related steps
"""

import contextlib
import logging
import tempfile
from collections import defaultdict
from pathlib import Path
from pprint import pformat
from typing import Dict, List, NamedTuple, Optional, Union

from retina.client.core import storage
from retina.client.manager import RetinaTestManager
from retina.launcher.artifacts import RetinaTestData

from .test_loader import RetinaNodeTypeDefinition, RetinaTestDefinition


# pylint: disable=too-many-arguments,too-many-positional-arguments
# pylint: disable=too-many-locals
def configure_test_parameters(
    *,  # This enforces keyword-only arguments
    retina_manager: RetinaTestManager,
    retina_data: RetinaTestData,
    band: int,
    common_scs: int,
    bandwidth: int,
    sample_rate: Optional[int],
    global_timing_advance: int,
    time_alignment_calibration: Union[int, str],
    n3_enable: Optional[bool] = None,
    common_search_space_enable: bool = False,
    prach_config_index: int = -1,
    log_ip_level: str = "",
    ul_noise_spd: int = 0,
    enable_security_mode: bool = False,
    rx_to_tx_latency: int = -1,
    enable_dddsu: bool = False,
    nof_antennas_dl: int = 1,
    nof_antennas_ul: int = 1,
    ims_mode: str = "",
    enable_drx: bool = False,
    pdsch_mcs_table: str = "qam256",
    pusch_mcs_table: str = "qam256",
    cu_cp_inactivity_timer: int = -1,
    pdsch_interleaving_bundle_size: int = 0,
    pdcch_log: bool = False,
    warning_allowlist: Optional[List[str]] = None,
):
    """
    Configure test parameters
    """
    ue_cell_bands = [
        {
            "band": band,
            "bandwidth": bandwidth,
            "dl_nr_arfcn": _get_dl_arfcn(band),
            "ssb_nr_arfcn": _get_ssb_arfcn(band, bandwidth),
            "subcarrier_spacing": common_scs,
            "ssb_subcarrier_spacing": common_scs,
        }
    ]

    retina_data.test_config = {
        "ue": {
            "parameters": {
                "global_timing_advance": global_timing_advance,
                "log_ip_level": log_ip_level,
                "ul_noise_spd": ul_noise_spd,
                "noise_spd": 0,
                "num_cells": 1,
                "cell_position_offset": (1000, 0, 0),
                "rx_to_tx_latency": rx_to_tx_latency,
                "nof_antennas_dl": nof_antennas_dl,
                "nof_antennas_ul": nof_antennas_ul,
                "pdcch_log": pdcch_log,
                "pdcch_decode_opt_threshold": 0,
                "ue_sds": [],
                "cells": ue_cell_bands,
            },
        },
        "gnb": {
            "node_list": [],
            "parameters": {
                "gnb_id_bit_length": 22,
                "band": band,
                "dl_arfcn": _get_dl_arfcn(band),
                "common_scs": common_scs,
                "bandwidth": bandwidth,
                "time_alignment_calibration": time_alignment_calibration,
                "common_search_space_enable": common_search_space_enable,
                "prach_config_index": prach_config_index,
                "enable_channel_noise": False,
                "enable_qos_reestablishment": False,
                "num_cells": 1,
                "enable_security_mode": enable_security_mode,
                "enable_dddsu": enable_dddsu,
                "nof_antennas_dl": nof_antennas_dl,
                "nof_antennas_ul": nof_antennas_ul,
                "enable_drx": enable_drx,
                "pdsch_mcs_table": pdsch_mcs_table,
                "pusch_mcs_table": pusch_mcs_table,
                "cu_cp_inactivity_timer": cu_cp_inactivity_timer,
                "pucch_formats": "f1_and_f2",
                "pdsch_interleaving_bundle_size": pdsch_interleaving_bundle_size,
                "slices": [],
                "warning_allowlist": warning_allowlist if warning_allowlist is not None else [],
            },
        },
        "du": {
            "node_list": [],
            "parameters": {
                "band": band,
                "dl_arfcn": _get_dl_arfcn(band),
                "common_scs": common_scs,
                "bandwidth": bandwidth,
                "time_alignment_calibration": time_alignment_calibration,
                "common_search_space_enable": common_search_space_enable,
                "prach_config_index": prach_config_index,
                "enable_channel_noise": False,
                "enable_qos_reestablishment": False,
                "enable_dddsu": enable_dddsu,
                "nof_antennas_dl": nof_antennas_dl,
                "nof_antennas_ul": nof_antennas_ul,
                "enable_drx": enable_drx,
                "pdsch_mcs_table": pdsch_mcs_table,
                "pusch_mcs_table": pusch_mcs_table,
                "pucch_formats": "f1_and_f2",
                "pdsch_interleaving_bundle_size": pdsch_interleaving_bundle_size,
                "slices": [],
            },
        },
        "cu": {
            "parameters": {
                "enable_security_mode": enable_security_mode,
                "cu_cp_inactivity_timer": cu_cp_inactivity_timer,
                "num_cells": 1,
            },
        },
        "5gc": {
            "parameters": {
                "ims_mode": ims_mode,
                "slices": [],
            }
        },
    }
    if n3_enable is not None and n3_enable:
        retina_data.test_config["gnb"]["parameters"]["pcap"] = True
        retina_data.test_config["gnb"]["parameters"]["n3_enable"] = True
    if sample_rate is not None:
        retina_data.test_config["ue"]["parameters"]["sample_rate"] = sample_rate
        retina_data.test_config["gnb"]["parameters"]["sample_rate"] = sample_rate
    if is_tdd(band):
        retina_data.test_config["ue"]["parameters"]["rx_ant"] = "rx"

    logging.debug("Test config: \n%s", pformat(retina_data.test_config))
    retina_manager.parse_configuration(retina_data.test_config)
    retina_manager.push_all_config()


def is_tdd(band: int) -> bool:
    """
    Return True if the band is tdd
    """
    return band in (41, 78)


def _get_dl_arfcn(band: int) -> int:
    """
    Get dl arfcn
    """
    return {3: 368500, 7: 536020, 41: 520002, 78: 632628, 256: 437000, 261: 2074171}[band]


def _get_ul_arfcn(band: int) -> int:
    """
    Get dl arfcn
    """
    return {3: 349500, 7: 512020, 41: 520002, 78: 632628, 256: 399000}[band]


def _get_ssb_arfcn(band: int, bandwidth: int) -> int:
    """
    Get SSB arfcn
    """
    return {  # type: ignore
        3: defaultdict(
            lambda: 368500,
            {
                5: 368410,
                10: 367930,
                20: 366970,
                30: 366010,
                40: 365050,
                50: 364090,
            },
        ),
        7: defaultdict(
            lambda: 535930,
            {
                20: 534490,
                30: 533530,
                40: 532570,
                50: 531610,
            },
        ),
        41: defaultdict(
            lambda: 519870,
            {
                20: 518910,
                30: 517950,
                40: 516990,
                50: 516030,
                100: 511950,
            },
        ),
        78: defaultdict(
            lambda: 632544,
            {
                20: 632256,
                30: 631968,
                40: 631680,
                50: 631296,
            },
        ),
        256: defaultdict(
            lambda: 437090,
            {
                5: 437090,
            },
        ),
        261: defaultdict(
            lambda: 2073691,
            {
                100: 2073691,
            },
        ),
    }[band][bandwidth]


def get_minimum_sample_rate_for_bandwidth(bandwidth: int) -> int:
    """
    Get the smallest sample rate for the selected bandwidth
    """
    f_s_list = [5.76, 7.68, 11.52, 15.36, 23.04, 30.72, 61.44, 122.88, 245.76]
    f_s_min = int(1e6 * min(filter(lambda f: f > bandwidth, f_s_list)))
    return f_s_min


class _NodeConfig(NamedTuple):
    attr: str  # attribute on RetinaTestDefinition
    config_folder: str  # Config folder
    templates: list  # template names expected by the retina API


_NODE_CONFIGS: Dict[storage.NodeTypeEnum, _NodeConfig] = {
    storage.NodeTypeEnum.UE: _NodeConfig("ue", "ue", ["ue"]),
    storage.NodeTypeEnum.CU: _NodeConfig("cu", "gnb", ["cu", "qos"]),
    storage.NodeTypeEnum.CU_CP: _NodeConfig("cu_cp", "gnb", ["cu", "qos"]),
    storage.NodeTypeEnum.CU_UP: _NodeConfig("cu_up", "gnb", ["cu", "qos"]),
    storage.NodeTypeEnum.DU: _NodeConfig("du", "gnb", ["du", "qos"]),
    storage.NodeTypeEnum.GNB: _NodeConfig("gnb", "gnb", ["cu", "du", "qos"]),
    storage.NodeTypeEnum.FIVEGC: _NodeConfig("core", "core", ["core", "ims"]),
}


def set_config_files(
    retina_manager: RetinaTestManager, retina_data: RetinaTestData, test_definition: RetinaTestDefinition
):
    """
    Overwrite default config files with the provided ones
    """
    with contextlib.ExitStack() as stack:
        retina_data.test_config = {}

        for node_type, node_cfg in _NODE_CONFIGS.items():
            item: RetinaNodeTypeDefinition = getattr(test_definition, node_cfg.attr)
            if not item.config and not item.parameters and not item.items:
                continue

            retina_data.test_config[node_type.value] = {}
            if item.config:
                retina_data.test_config[node_type.value]["templates"] = _build_templates(stack, node_cfg, item.config)
            if item.parameters:
                retina_data.test_config[node_type.value]["parameters"] = item.parameters
            if item.items:
                retina_data.test_config[node_type.value]["node_list"] = [
                    {
                        "name": storage.clients[node_type][i].name,
                        **(
                            {"templates": _build_templates(stack, node_cfg, [*item.config, *child.config])}
                            if child.config
                            else {}
                        ),
                        **({"parameters": child.parameters} if child.parameters else {}),
                    }
                    for i, child in enumerate(item.items)
                ]

        retina_manager.parse_configuration(retina_data.test_config)
        retina_manager.push_all_config()


def _build_templates(stack: contextlib.ExitStack, node_cfg: _NodeConfig, config_files: list[str]) -> Dict:
    main, *extras = node_cfg.templates

    merged = stack.enter_context(tempfile.NamedTemporaryFile(mode="w+"))  # pylint: disable=consider-using-with
    for cfg_file in config_files:
        merged.write(
            (Path(__file__).parent.parent / "configs" / node_cfg.config_folder / cfg_file).read_text(encoding="UTF-8")
        )
        merged.write("\n")
    merged.flush()

    empty_file = stack.enter_context(tempfile.NamedTemporaryFile(mode="w+"))  # pylint: disable=consider-using-with
    empty_file.write(" ")  # Must be non-empty to overwrite default
    empty_file.flush()

    return {
        main: merged.name,
        **{extra: empty_file.name for extra in extras},
    }
