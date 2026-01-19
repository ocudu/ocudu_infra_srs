#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
NTN Channel Emulator Agent
"""

import logging
from typing import Any, Dict, Tuple

import grpc
import yaml
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from retina.protocol.base_pb2 import ChannelEmulatorDefinition, ChannelEmulatorType, DUDefinition, UEDefinition
from retina.protocol.channel_emulator_pb2 import (
    ChannelEmulatorStartInfo,
    ChannelEmulatorSummary,
    EphemerisInfoType,
    NtnScenarioConfig,
    NtnScenarioDefinition,
    NtnScenarioType,
    ScenarioConfig,
    Sib19Config,
    TaSchedConfig,
    UePosition,
)

from retina.agent.drivers.base import notify_grpc_exception
from retina.agent.drivers.channel_emulator import ChannelEmulatorDriver
from retina.agent.features.executor import LocalExecutor
from retina.agent.features.sut_handler import BaseDriverSutHandler
from retina.agent.features.utils import get_module_variables
from retina.agent.parameters import template_defaults, testbed_defaults


class NtnChannelEmulator(ChannelEmulatorDriver, BaseDriverSutHandler):
    """
    NTN Channel Emulator Agent
    """

    EMULATOR_BINARY_NAME: str = "/ntn-channel-emulator/channel-emulator.py"
    EMULATOR_STDOUT_NAME: str = "stdout"
    EMULATOR_CONF_FILE_BASE_NAME: str = "ntn_channel_emulator.yml"
    EMULATOR_START_UP_TIMEOUT: int = 20  # It can take a while to generate a NTN scenario.
    OCUDU_NTN_CONFIG_FN: str = "ocudu_ntn.yml"
    UE_POSITION_FN: str = "ue-position.cfg"
    UE_GS_POSITION_FN: str = "gs-position.cfg"
    EMULATOR_UE_POSITION_FN: str = "emulator-ue-position.cfg"
    GEO_TLE_FN: str = "/ntn-channel-emulator/tle_data/example_geo_tle.txt"
    LEO_TLE_FN: str = "/ntn-channel-emulator/tle_data/example_leo_tle.txt"

    def __init__(self, *args, **kwargs) -> None:
        self.logfile = None
        self.summary_report = ChannelEmulatorSummary()
        super().__init__(*args, **kwargs)

    def _get_sut_version(self) -> str:
        return ""

    def GetDefinition(self, request: Empty, context: grpc.ServicerContext) -> ChannelEmulatorDefinition:
        return ChannelEmulatorDefinition(
            type=ChannelEmulatorType.NTN,
            zmq_ip=testbed_defaults.ip_zmq,
            dl_zmq_port=testbed_defaults.port_array[0],
            ul_zmq_port=testbed_defaults.port_array[1],
        )

    def get_parameters(
        self, *, ntn_scenario: NtnScenarioDefinition, du: DUDefinition, ue: UEDefinition
    ) -> Dict[str, Any]:
        """
        Return parameters for config templates
        """
        return {
            "gnb_zmq_ip": du.zmq_ip,
            "gnb_zmq_port": du.zmq_port_array[0],
            "ue_zmq_ip": ue.zmq_ip,
            "ue_zmq_port": ue.zmq_port_array[0],
            "tle_fn": self.GEO_TLE_FN if ntn_scenario.scenario_type == NtnScenarioType.GEO else self.LEO_TLE_FN,
            "sib19_format": "orbital" if ntn_scenario.ephemeris_info_type == EphemerisInfoType.ORBITAL else "ecef",
            "gnb_ntn_config_fn": self.get_filepath_in_report_folder(self.OCUDU_NTN_CONFIG_FN),
            "ue_position_fn": self.get_filepath_in_report_folder(self.UE_POSITION_FN),
            "amariue_position_fn": self.get_filepath_in_report_folder(self.EMULATOR_UE_POSITION_FN),
            "amariue_gs_position_fn": self.get_filepath_in_report_folder(self.UE_GS_POSITION_FN),
            "pass_start_offset_s": ntn_scenario.pass_start_offset_s,
            "delay_offset_us": ntn_scenario.delay_offset_us,
            "min_sat_elevation_deg": ntn_scenario.min_sat_elevation_deg,
            "sample_rate": ntn_scenario.sample_rate,
            "enable_doppler": ntn_scenario.enable_doppler,
            "al_dl_freq_hz": ntn_scenario.access_link_dl_freq_hz,
            "al_ul_freq_hz": ntn_scenario.access_link_ul_freq_hz,
            "enable_feeder_link": ntn_scenario.enable_feeder_link,
            "fl_dl_freq_hz": ntn_scenario.feeder_link_dl_freq_hz,
            "fl_ul_freq_hz": ntn_scenario.feeder_link_ul_freq_hz,
        }

    def Start(self, request: ChannelEmulatorStartInfo, context: grpc.ServicerContext) -> Empty:
        self.Stop(UInt32Value(value=request.start_info.timeout), context)

        # Reset Summary Report
        self.summary_report = ChannelEmulatorSummary()

        ntn_scenario = None
        if request.HasField("ntn_scenario"):
            ntn_scenario = request.ntn_scenario

        if ntn_scenario is None:
            logging.info("Cannot start NTN Channel Emulator.")
            return Empty()

        config_file = self._render(
            filename=self.EMULATOR_CONF_FILE_BASE_NAME,
            templates={self.EMULATOR_CONF_FILE_BASE_NAME: template_defaults.main},
            values={
                **get_module_variables(testbed_defaults),
                **self.get_parameters(ntn_scenario=ntn_scenario, du=request.du_definition, ue=request.ue_definition),
            },
        )

        # Launch
        self.logfile = self.get_filepath_in_report_folder(self.EMULATOR_STDOUT_NAME) + ".log"
        self._last_log_array = (self.logfile,)

        self.start_sut(
            *(item for pre_command in request.start_info.pre_commands for item in pre_command.split(" ")),
            "python3",
            "-u",
            self.EMULATOR_BINARY_NAME,
            "--config",
            config_file,
            *(item for post_command in request.start_info.post_commands for item in post_command.split(" ")),
            dryrun=request.start_info.dryrun,
            logfile=self.logfile,
        )

        # Wait until the NTN Channel Emulator is is up and running
        if not request.start_info.dryrun:
            try:
                self.read_from_log(
                    (r"Channel Emulator Started",),
                    True,
                    timeout=(
                        request.start_info.timeout if request.start_info.timeout else self.EMULATOR_START_UP_TIMEOUT
                    ),
                )
            except TimeoutError as err:
                logging.warning("Timeout reached while looking for NTN Channel Emulator starting reference.")
                if not self._is_alive:
                    with notify_grpc_exception(context):
                        raise err from None

        logging.info("NTN Channel Emulator started")
        return Empty()

    def load_ue_coords_from_file(self, filename):
        """
        Read the UE position from the ue-position.cfg file.
        """
        data = {}
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line.startswith("latitude:"):
                    data["latitude"] = float(line.split(":")[1].strip().rstrip(","))
                elif line.startswith("longitude:"):
                    data["longitude"] = float(line.split(":")[1].strip().rstrip(","))
                elif line.startswith("altitude:"):
                    data["altitude"] = int(line.split(":")[1].strip().rstrip(","))
        return data

    def fill_ue_position(self, ue_position: UePosition):
        """
        Put the UE position into NtnScenarioConfig.
        """
        ue_pos = self.load_ue_coords_from_file(self.get_filepath_in_report_folder(self.UE_POSITION_FN))
        logging.info(ue_pos)
        ue_position.latitude = ue_pos["latitude"]
        ue_position.longitude = ue_pos["longitude"]
        ue_position.altitude = ue_pos["altitude"]

    def fill_ta_sched_cfg(self, ta_sched_cfg: TaSchedConfig):
        """
        Put the TA-related config into NtnScenarioConfig.
        """
        path = self.get_filepath_in_report_folder(self.OCUDU_NTN_CONFIG_FN)
        ocudu_gnb_cfg = None
        with open(path, "r", encoding="utf-8") as file:
            ocudu_gnb_cfg = yaml.safe_load(file)
            ta_sched_cfg_dict = ocudu_gnb_cfg["cell_cfg"]["ta"]
            ta_sched_cfg.ta_target = ta_sched_cfg_dict["ta_target"]
            ta_sched_cfg.slot_prohibit_period = ta_sched_cfg_dict["ta_measurement_slot_prohibit_period"]
            ta_sched_cfg.slot_meas_period = ta_sched_cfg_dict["ta_measurement_slot_period"]
            ta_sched_cfg.ta_cmd_offset_threshold = ta_sched_cfg_dict["ta_cmd_offset_threshold"]

    def fill_sib19_cfg(self, sib19_cfg: Sib19Config):
        """
        Put the initial SIB19 config into NtnScenarioConfig.
        """
        path = self.get_filepath_in_report_folder(self.OCUDU_NTN_CONFIG_FN)
        ocudu_gnb_cfg = None
        with open(path, "r", encoding="utf-8") as file:
            ocudu_gnb_cfg = yaml.safe_load(file)

        ntn_cfg = ocudu_gnb_cfg["ntn"]
        sib19_cfg.epoch_time_sfn = 0  # gnb overwrites it
        sib19_cfg.epoch_time_subframe_number = 0  # gnb overwrites it
        sib19_cfg.ntn_ul_sync_validity_dur = ntn_cfg["ntn_ul_sync_validity_dur"]
        sib19_cfg.cell_specific_koffset = ntn_cfg["cell_specific_koffset"]
        sib19_cfg.ta_common = ntn_cfg["ta_info"]["ta_common"]
        sib19_cfg.ta_common_drift = ntn_cfg["ta_info"]["ta_common_drift"]
        sib19_cfg.ta_common_drift_variant = ntn_cfg["ta_info"]["ta_common_drift_variant"]

        if "ephemeris_orbital" in ntn_cfg:
            sib19_cfg.ephemeris_info_type = EphemerisInfoType.ORBITAL
            orbital = ntn_cfg["ephemeris_orbital"]
            sib19_cfg.ephemeris_orbital.semi_major_axis = orbital["semi_major_axis"]
            sib19_cfg.ephemeris_orbital.eccentricity = orbital["eccentricity"]
            sib19_cfg.ephemeris_orbital.periapsis = orbital["periapsis"]
            sib19_cfg.ephemeris_orbital.longitude = orbital["longitude"]
            sib19_cfg.ephemeris_orbital.inclination = orbital["inclination"]
            sib19_cfg.ephemeris_orbital.mean_anomaly = orbital["mean_anomaly"]
        else:
            ecef_params = ntn_cfg["ephemeris_info_ecef"]
            sib19_cfg.ephemeris_info_type = EphemerisInfoType.ECEF
            sib19_cfg.ephemeris_info_ecef.pos_x = ecef_params["pos_x"]
            sib19_cfg.ephemeris_info_ecef.pos_y = ecef_params["pos_y"]
            sib19_cfg.ephemeris_info_ecef.pos_z = ecef_params["pos_z"]
            sib19_cfg.ephemeris_info_ecef.vel_x = ecef_params["vel_x"]
            sib19_cfg.ephemeris_info_ecef.vel_y = ecef_params["vel_y"]
            sib19_cfg.ephemeris_info_ecef.vel_z = ecef_params["vel_z"]

    def GetScenarioConfigs(self, request: Empty, context: grpc.ServicerContext) -> ScenarioConfig:
        scenario_config = ScenarioConfig()
        ntn_config = NtnScenarioConfig()
        self.fill_sib19_cfg(ntn_config.sib19_cfg)
        self.fill_ta_sched_cfg(ntn_config.ta_cfg)
        self.fill_ue_position(ntn_config.ue_position)

        scenario_config.ntn_config.CopyFrom(ntn_config)
        return scenario_config

    def GetChannelEmulatorSummary(self, request: Empty, context: grpc.ServicerContext) -> ChannelEmulatorSummary:
        self.summary_report.placeholder = 1
        return self.summary_report

    @property
    def _expected_exit_code_array(self) -> Tuple[int, ...]:
        return (-9, -15, -137)


class LocalNtnChannelEmulator(NtnChannelEmulator):
    """
    NTN Channel Emulator Agent for local
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, executor=LocalExecutor())
