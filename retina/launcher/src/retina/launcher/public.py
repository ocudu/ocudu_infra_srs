#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Fixtures to use from tests
"""

import logging
import operator
from contextlib import suppress
from pathlib import Path
from statistics import mean
from typing import Callable, Dict, Generator, Optional, Sequence, Tuple

import grpc
import pytest
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import UInt32Value
from requests import HTTPError
from retina.client.exception import ErrorReportedByAgent
from retina.client.manager import RetinaTestManager
from retina.protocol import RanStub
from retina.protocol.base_pb2 import Metrics, StopResponse
from retina.protocol.channel_emulator_pb2_grpc import ChannelEmulatorStub
from retina.protocol.exit_codes import exit_code_to_message
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import CUStub, DUStub, GNBStub
from retina.protocol.resource import API, Core, Remote
from retina.protocol.ric_pb2_grpc import NearRtRicStub
from retina.protocol.ue_pb2_grpc import UEStub
from retina.viavi.client import CampaignStatusEnum, Viavi

from retina.launcher.artifacts import RetinaTestData, TEST_SUCCESS_FIELD
from retina.launcher.criteria import Criteria
from retina.launcher.reporter import create_report


@pytest.fixture
def no_logs_in_error(
    caplog: pytest.LogCaptureFixture,
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """
    Raise an AssertionError if there are errors in the log
    """
    yield
    test_success: bool = getattr(request.node, TEST_SUCCESS_FIELD, True)
    if test_success:
        # If the test has failed, no need to fail again due to error in the logs
        errors = [record.message for record in caplog.records if record.levelno >= logging.ERROR]
        if errors:
            pytest.fail("Setup / Teardown failed due to following unhandled errors: \n - " + "\n - ".join(errors))


@pytest.fixture
def retina_manager(
    test_log_folder: str,
    orchestration: Dict,
    register_parameter: Tuple[Tuple[str, Optional[str], str, str], ...],
    register_template: Tuple[Tuple[str, Optional[str], str, str], ...],
    no_logs_in_error: None,
) -> Generator[RetinaTestManager, None, None]:
    """
    Start retina test manager, set folder and parse tested and parameters
    """

    try:
        retina_manager_obj = RetinaTestManager()
        retina_manager_obj.set_report_folder(test_log_folder)
        retina_manager_obj.parse_testbed(orchestration)
        for kind, name, key, value in register_parameter:
            retina_manager_obj.register_parameter(kind, name, key, value)
        for kind, name, key, value in register_template:
            retina_manager_obj.register_template(kind, name, key, value)
        yield retina_manager_obj
    finally:
        try:
            # Close clients
            retina_manager_obj.close_all()
        except Exception as err:  # pylint: disable=broad-exception-caught
            logging.exception(err)


@pytest.fixture
def retina_data(
    request: pytest.FixtureRequest,
    retina_manager: RetinaTestManager,
    force_download: bool,
    test_log_folder: str,
) -> Generator[RetinaTestData, None, None]:
    """
    Share retina data with test call and download artifacts at teardown
    """
    try:
        retina_test_data = RetinaTestData(force_download, {})

        # Yield to run the test
        yield retina_test_data

    finally:
        # Download artifacts
        test_success: bool = getattr(request.node, TEST_SUCCESS_FIELD, True)
        if not test_success or retina_test_data.download_artifacts:
            try:
                retina_manager.download_all_artifacts()
            except grpc.RpcError as err:
                logging.error(ErrorReportedByAgent(err))
            except Exception as err:  # pylint: disable=broad-exception-caught
                logging.exception(err)
        # Create report
        create_report(
            test_log_folder,
            str(Path(request.config.getoption("htmlpath")).resolve()),
            retina_test_data.test_config,
            request.node.name,
            retina_manager.get_testbed_info(),
        )


@pytest.fixture
# pylint: disable=invalid-name
def ue(retina_manager: RetinaTestManager, retina_data: RetinaTestData) -> Generator[UEStub, None, None]:
    """
    Return an UE
    """
    try:
        ue_stub = retina_manager.get_ue()
        yield ue_stub
    finally:
        with suppress(NameError, UnboundLocalError):
            _stop_stub(ue_stub, "UE", retina_data)


def _generate_ue_fixture(number_of_ues: int) -> Callable:
    @pytest.fixture
    # pylint: disable=invalid-name
    def ue_multiple(
        retina_manager: RetinaTestManager, retina_data: RetinaTestData
    ) -> Generator[Tuple[UEStub, ...], None, None]:
        """
        Return multiple UEs
        """
        try:
            ue_stub_array = tuple(retina_manager.get_ue(index) for index in range(number_of_ues))
            yield ue_stub_array
        finally:
            with suppress(NameError, UnboundLocalError):
                for index, ue_stub in enumerate(ue_stub_array):
                    _stop_stub(ue_stub, f"UE_{index+1}", retina_data)

    return ue_multiple


for n in range(1, 1000 + 1):
    globals()[f"ue_{n}"] = _generate_ue_fixture(n)


def _generate_gnb_fixture(number_of_gnbs: int) -> Callable:
    @pytest.fixture
    # pylint: disable=invalid-name
    def gnb_multiple(
        retina_manager: RetinaTestManager, retina_data: RetinaTestData, criteria: Criteria
    ) -> Generator[Tuple[GNBStub, ...], None, None]:
        """
        Return multiple GNBs
        """
        try:
            gnb_stub_array = tuple(retina_manager.get_gnb(index) for index in range(number_of_gnbs))
            _register_du_criteria(criteria, gnb_stub_array)
            yield gnb_stub_array
        finally:
            with suppress(NameError, UnboundLocalError):
                for index, gnb_stub in enumerate(gnb_stub_array):
                    _stop_stub(gnb_stub, f"GNB_{index+1}", retina_data)

    return gnb_multiple


for n in range(1, 64 + 1):
    globals()[f"gnb_{n}"] = _generate_gnb_fixture(n)


@pytest.fixture
def gnb(
    retina_manager: RetinaTestManager, retina_data: RetinaTestData, criteria: Criteria
) -> Generator[GNBStub, None, None]:
    """
    Return a GNB
    """
    try:
        gnb_stub = retina_manager.get_gnb()
        _register_du_criteria(criteria, (gnb_stub,))
        yield gnb_stub
    finally:
        with suppress(NameError, UnboundLocalError):
            _stop_stub(gnb_stub, "GNB", retina_data)


@pytest.fixture
def cu(retina_manager: RetinaTestManager, retina_data: RetinaTestData) -> Generator[CUStub, None, None]:
    """
    Return a CU
    """
    try:
        cu_stub = retina_manager.get_cu()
        yield cu_stub
    finally:
        with suppress(NameError, UnboundLocalError):
            _stop_stub(cu_stub, "CU", retina_data)


@pytest.fixture
# pylint: disable=invalid-name
def du(
    retina_manager: RetinaTestManager, retina_data: RetinaTestData, criteria: Criteria
) -> Generator[DUStub, None, None]:
    """
    Return an DU
    """
    try:
        du_stub = retina_manager.get_du()
        _register_du_criteria(criteria, (du_stub,))
        yield du_stub
    finally:
        with suppress(NameError, UnboundLocalError):
            _stop_stub(du_stub, "DU", retina_data)


def _generate_du_fixture(number_of_dus: int) -> Callable:
    @pytest.fixture
    # pylint: disable=invalid-name
    def du_multiple(
        retina_manager: RetinaTestManager, retina_data: RetinaTestData, criteria: Criteria
    ) -> Generator[Tuple[DUStub, ...], None, None]:
        """
        Return multiple DUs
        """
        try:
            du_stub_array = tuple(retina_manager.get_du(index) for index in range(number_of_dus))
            _register_du_criteria(criteria, du_stub_array)
            yield du_stub_array
        finally:
            with suppress(NameError, UnboundLocalError):
                for index, du_stub in enumerate(du_stub_array):
                    _stop_stub(du_stub, f"DU_{index+1}", retina_data)

    return du_multiple


for n in range(1, 64 + 1):
    globals()[f"du_{n}"] = _generate_du_fixture(n)


def _register_du_criteria(
    criteria: Criteria, du_or_gnb_array: Sequence[RanStub]
):  # pylint: disable=redefined-outer-name
    criteria.register_available_criteria(
        "dl_bitrate",
        "DL bitrate",
        lambda: mean(gnb_stub.GetMetrics(Empty()).total.dl_bitrate for gnb_stub in du_or_gnb_array),
        operator.gt,
    )
    criteria.register_available_criteria(
        "ul_bitrate",
        "UL bitrate",
        lambda: mean(gnb_stub.GetMetrics(Empty()).total.ul_bitrate for gnb_stub in du_or_gnb_array),
        operator.gt,
    )
    criteria.register_available_criteria(
        "nof_ko_dl",
        "DL KOs",
        lambda: sum(gnb_stub.GetMetrics(Empty()).total.dl_nof_ko for gnb_stub in du_or_gnb_array),
        operator.le,
    )
    criteria.register_available_criteria(
        "nof_ko_ul",
        "UL KOs",
        lambda: sum(gnb_stub.GetMetrics(Empty()).total.ul_nof_ko for gnb_stub in du_or_gnb_array),
        operator.le,
    )
    criteria.register_available_criteria(
        "max_late_dl_harqs",
        "Late DL HARQs",
        lambda: sum(gnb_stub.GetMetrics(Empty()).cell.max_late_dl_harqs for gnb_stub in du_or_gnb_array),
        operator.le,
    )
    criteria.register_available_criteria(
        "max_late_ul_harqs",
        "Late UL HARQs",
        lambda: sum(gnb_stub.GetMetrics(Empty()).cell.max_late_ul_harqs for gnb_stub in du_or_gnb_array),
        operator.le,
    )
    criteria.register_available_criteria(
        "nof_error_indications",
        "Error Indications",
        lambda: sum(gnb_stub.GetMetrics(Empty()).cell.error_indication_cnt for gnb_stub in du_or_gnb_array),
        operator.le,
    )
    criteria.register_available_criteria(
        "nof_reestablishments",
        "Reestablishments",
        lambda: sum(gnb_stub.GetMetrics(Empty()).total.nof_reestablishments_complete for gnb_stub in du_or_gnb_array),
        operator.eq,
    )
    criteria.register_available_criteria(
        "nof_handovers",
        "Handovers",
        lambda: sum(gnb_stub.GetMetrics(Empty()).total.nof_handovers for gnb_stub in du_or_gnb_array),
        operator.eq,
    )
    criteria.register_available_criteria(
        "errors",
        "Errors",
        lambda: sum(
            gnb_stub.Stop.with_call(UInt32Value(value=15), timeout=15)[0].error_count for gnb_stub in du_or_gnb_array
        ),
        operator.le,
    )
    criteria.register_available_criteria(
        "warnings",
        "Warnings",
        lambda: sum(
            gnb_stub.Stop.with_call(UInt32Value(value=15), timeout=15)[0].warning_count for gnb_stub in du_or_gnb_array
        ),
        operator.le,
    )


@pytest.fixture
def fivegc(retina_manager: RetinaTestManager, retina_data: RetinaTestData) -> Generator[FiveGCStub, None, None]:
    """
    Return a 5GC
    """
    try:
        fivegc_stub = retina_manager.get_5gc()
        yield fivegc_stub
    finally:
        with suppress(NameError, UnboundLocalError):
            _stop_stub(fivegc_stub, "5GC", retina_data)


@pytest.fixture
def ric(retina_manager: RetinaTestManager, retina_data: RetinaTestData) -> Generator[NearRtRicStub, None, None]:
    """
    Return a RIC
    """
    try:
        ric_stub = retina_manager.get_ric()
        yield ric_stub
    finally:
        with suppress(NameError, UnboundLocalError):
            _stop_stub(ric_stub, "RIC", retina_data)


@pytest.fixture
def channel_emulator(
    retina_manager: RetinaTestManager, retina_data: RetinaTestData
) -> Generator[ChannelEmulatorStub, None, None]:
    """
    Return a Channel Emulator
    """
    try:
        channel_emulator_stub = retina_manager.get_channel_emulator()
        yield channel_emulator_stub
    finally:
        with suppress(NameError, UnboundLocalError):
            _stop_stub(channel_emulator_stub, "CHANNEL_EMULATOR", retina_data)


# pylint: disable=redefined-outer-name
def _stop_stub(
    stub: RanStub,
    name: str,
    retina_data: RetinaTestData,
    rpc_timeout: int = 300,
) -> None:
    """
    Stop a stub in the defined timeout (0=auto).
    It uses retina_data to save artifacts in case of failure
    """

    try:
        # Stop
        stop_info: StopResponse = stub.Stop.with_call(UInt32Value(value=15), timeout=rpc_timeout)[0]
        if stop_info.exit_code:
            retina_data.download_artifacts = True
            logging.error(
                "%s crashed with exit code %d (%s)",
                name,
                stop_info.exit_code,
                exit_code_to_message(stop_info.exit_code),
            )
        else:
            logging.info("%s has successfully stopped", name)
        if stop_info.error_count or stop_info.warning_count:
            log_msg = f"{name} has {stop_info.error_count} errors and {stop_info.warning_count} warnings. "
            if stop_info.error_count:
                log_msg += f"First error is: {stop_info.error_msg}"
            elif stop_info.warning_count:
                log_msg += f"First warning is: {stop_info.warning_msg}"
            logging.warning(log_msg)
    except grpc.RpcError as err:
        logging.error("%s stop %s.", name, ErrorReportedByAgent(err))

    _log_metrics(stub, name)


def _log_metrics(
    stub: RanStub,
    name: str,
) -> None:
    try:
        metrics: Metrics = stub.GetMetrics(Empty())
        for ue_info in metrics.ue_array:
            nof_kos = ue_info.dl_nof_ko + ue_info.ul_nof_ko
            if nof_kos:
                logging.warning(
                    "%s: [UE pci: %s rnti: %s] has %s KOs / retrxs", name, ue_info.pci, ue_info.rnti, nof_kos
                )
        if metrics.system.nof_lates:
            logging.warning("%s has %s UHD Lates", name, metrics.system.nof_lates)
        if metrics.system.nof_under:
            logging.warning("%s has %s UHD Underflows", name, metrics.system.nof_under)
        if metrics.system.nof_seq_err:
            logging.warning("%s has %s UHD Sequence errors", name, metrics.system.nof_seq_err)
    except grpc.RpcError:
        logging.error("%s metrics couldn't be recovered.", name)


@pytest.fixture
def viavi(
    retina_manager: RetinaTestManager, retina_data: RetinaTestData, criteria: Criteria
) -> Generator[Viavi, None, None]:  # pylint: disable=too-many-nested-blocks
    """
    Return a Viavi Controller
    """

    viavi_client = None
    for nodes_by_type_dict in retina_manager.get_testbed_info().values():
        for node_info in nodes_by_type_dict.values():
            remote: Remote
            api: API
            core: Core
            for resource in node_info.resources:
                if isinstance(resource, Remote):
                    remote = resource
                elif isinstance(resource, API):
                    api = resource
                elif isinstance(resource, Core):
                    core = resource
            if remote is not None or api is not None or core is not None:
                viavi_client = Viavi(
                    address=remote.address,
                    port=api.port,
                    username=remote.user,
                    password=remote.password,
                    tma_path=remote.path,
                    tma_profile="Default User",
                    amf_address=core.address,
                    amf_port=core.port,
                )
                break
        if viavi_client is not None:
            break
    else:
        # When no break -> no viavi def found
        raise KeyError("Viavi resource not found")

    try:
        with suppress(HTTPError):
            viavi_client.delete_tma()
        viavi_client.create_tma()

        # Register pass fail criteria
        criteria.register_available_criteria(
            "viavi_nof_ko_dl",
            "DL KOs (viavi)",
            lambda: viavi_client.get_test_kpis().dl_data.num_tbs_errors,
            operator.le,
        )
        criteria.register_available_criteria(
            "viavi_nof_ko_ul",
            "UL KOs (viavi)",
            lambda: viavi_client.get_test_kpis().ul_data.num_tbs_nack,
            operator.le,
        )
        criteria.register_available_criteria(
            "viavi_warnings",
            "Viavi Warnings",
            lambda: len(viavi_client.get_test_kpis().warning_array),
            operator.lt,
        )
        criteria.register_available_criteria(
            "viavi_procedure_table",
            "Procedure table",
            lambda: viavi_client.get_test_kpis().get_number_of_procedure_failures(["authentication"]),
            operator.eq,
        )

        yield viavi_client
    finally:
        # Stop running campaign
        with suppress(HTTPError):
            viavi_client.stop_running_campaign()
            # If last campaign failed, force artifacts download
            if viavi_client.get_running_campaign_info().status is CampaignStatusEnum.FAIL:
                retina_data.download_artifacts = True
                logging.error("Viavi last campaign failed")
        with suppress(HTTPError):
            viavi_client.delete_tma()


@pytest.fixture
def criteria(capsys: pytest.CaptureFixture[str]) -> Generator[Criteria, None, None]:
    """
    Return a Criteria instance for managing test pass/fail criteria.
    """
    yield Criteria(capsys=capsys)
