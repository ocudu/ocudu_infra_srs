# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Handle Retina Communication with the agent
"""

import logging
import socket
from contextlib import suppress
from random import randint
from threading import Event, Thread
from time import sleep, time
from typing import Any, Dict, Optional, Tuple, Type

import grpc
from google.protobuf.empty_pb2 import Empty
from grpc_health.v1.health_pb2 import HealthCheckRequest, HealthCheckResponse
from grpc_health.v1.health_pb2_grpc import HealthStub
from retina.protocol import RanStub
from retina.protocol.artifact import download_archived_artifact
from retina.protocol.base_pb2 import Parameter
from retina.protocol.base_pb2_grpc import BaseStub
from retina.protocol.channel_emulator_pb2_grpc import ChannelEmulatorStub
from retina.protocol.fivegc_pb2_grpc import FiveGCStub
from retina.protocol.gnb_pb2_grpc import CUStub, DUStub, GNBStub
from retina.protocol.ric_pb2_grpc import NearRtRicStub
from retina.protocol.ue_pb2_grpc import UEStub

from retina.client.core.communication_port import CommunicationPort, Version
from retina.client.exception import ErrorReportedByAgent


class GrpcAdaptor(CommunicationPort):
    """
    Handle Retina Communication with the agent. GRPC Adaptor
    """

    _KIND_CODENAME_DICT: Dict[str, Type[RanStub]] = {
        "ue": UEStub,
        "gnb": GNBStub,
        "cu": CUStub,
        "du": DUStub,
        "5gc": FiveGCStub,
        "ric": NearRtRicStub,
        "channel-emulator": ChannelEmulatorStub,
    }
    _DEFAULT_KEEP_ALIVE_PERIOD: int = 60

    def __init__(self, *args, **kwargs) -> None:
        self._grpc_channel_dict: Dict[RanStub, grpc.Channel] = {}
        self._thread_alive_dict: Dict[RanStub, Thread] = {}
        self._event_alive_dict: Dict[RanStub, Event] = {}
        self._stub_address_dict: Dict[RanStub, Tuple[str, int]] = {}
        super().__init__(*args, **kwargs)

    def create_client(self, node_type: str, *com_args) -> RanStub:
        ip_address, port = com_args

        interceptors = (
            _RetryOnRpcErrorClientInterceptor(
                max_attempts=10,
                status_for_retry=(grpc.StatusCode.UNAVAILABLE,),
            ),
        )
        channel = grpc.intercept_channel(
            grpc.insecure_channel(
                f"{ip_address}:{port}",
            ),
            *interceptors,
        )

        stub = BaseStub(channel)
        # pylint: disable=unnecessary-dunder-call
        HealthStub.__init__(stub, channel)
        self._wait_for_agent(stub)

        self._KIND_CODENAME_DICT[node_type].__init__(stub, channel)
        self._grpc_channel_dict[stub] = channel
        self._stub_address_dict[stub] = (ip_address, port)
        self._event_alive_dict[stub] = Event()
        self._thread_alive_dict[stub] = Thread(target=self._keep_alive, args=(stub, self._event_alive_dict[stub]))
        self._thread_alive_dict[stub].start()

        return stub

    def get_version(self, stub: RanStub) -> Version:
        client_version = stub.GetRetinaInfo(Empty())
        return Version(
            agent=client_version.agent_version,
            sut=client_version.sut_version,
        )

    @staticmethod
    def push_parameter(stub: RanStub, key: str, value: Any, param_namespace: str) -> None:
        stub.SetParameter(Parameter(name=f"{param_namespace}.{key}", value=str(value)))

    def _close_all_keep_alive(self) -> None:
        for stub in self._thread_alive_dict:  # pylint: disable=consider-using-dict-items
            if self._thread_alive_dict[stub].is_alive():
                self._event_alive_dict[stub].set()
                self._thread_alive_dict[stub].join()

    def close_client(self, stub: RanStub) -> None:
        # When closing, we need to first close all keep alive threads to avoid fake comm error messages reported
        self._close_all_keep_alive()
        if stub in self._grpc_channel_dict:
            ip, port = self._stub_address_dict[stub]
            with suppress(OSError, grpc.RpcError):
                with socket.create_connection((ip, port), timeout=1):
                    # Shutdown called only if the port can be open (the agent is still listening)
                    stub.Shutdown.with_call(Empty(), timeout=1)
            self._grpc_channel_dict[stub].close()

    @staticmethod
    def download_artifacts(stub: RanStub, report_folder: str) -> None:
        try:
            download_archived_artifact(stub, report_folder)
        except grpc.RpcError as err:
            logging.error(ErrorReportedByAgent(err))

    @staticmethod
    def get_artifact_id(stub: RanStub) -> str:
        try:
            return stub.GetArtifactsId(Empty()).value
        except grpc.RpcError as err:
            logging.error(ErrorReportedByAgent(err))
            return str(id(stub))

    @staticmethod
    def _wait_for_agent(stub: HealthStub, timeout: int = 30) -> None:
        deadline = time() + timeout
        while time() < deadline:
            try:
                response: HealthCheckResponse = stub.Check(HealthCheckRequest())
                if response.status == HealthCheckResponse.SERVING:
                    return
            except grpc.RpcError:
                pass
            sleep(1)
        raise TimeoutError(f"Agent not ready after {timeout}s")

    @staticmethod
    def _keep_alive(stub: HealthStub, event: Event, step: int = _DEFAULT_KEEP_ALIVE_PERIOD) -> None:
        """
        Keep alive a stub by sending a `GetRetinaInfo` method each `step` seconds.
        """
        while not event.is_set():
            try:
                response: HealthCheckResponse = stub.Check(HealthCheckRequest())
                if response.status is not HealthCheckResponse.SERVING:
                    logging.error(
                        "GRPC Health check failed: %s",
                        response.status,
                    )
            except grpc.RpcError as err:
                if ErrorReportedByAgent(err).code is not grpc.StatusCode.UNAVAILABLE:
                    raise err from None
                logging.error(ErrorReportedByAgent(err))
                event.set()  # Stop the keep alive thread
            finally:
                event.wait(step)


class _RetryOnRpcErrorClientInterceptor(grpc.UnaryUnaryClientInterceptor, grpc.StreamUnaryClientInterceptor):
    def __init__(
        self,
        *,
        max_attempts: int,
        status_for_retry: Optional[Tuple[grpc.StatusCode]] = None,
        min_backoff: int = 100,
        max_backoff: int = 5000,
    ):
        self.max_attempts = max_attempts if max_attempts > 1 else 1
        self.status_for_retry = status_for_retry
        self.min_backoff = min_backoff
        self.max_backoff = max_backoff

    def intercept_unary_unary(self, continuation, client_call_details, request):
        return self._intercept_call(continuation, client_call_details, request)

    def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        return self._intercept_call(continuation, client_call_details, request_iterator)

    def _intercept_call(self, continuation, client_call_details, request_or_iterator):
        for try_i in range(self.max_attempts):
            response = continuation(client_call_details, request_or_iterator)

            # pylint: disable=protected-access
            if isinstance(response, grpc._channel._MultiThreadedRendezvous):
                break

            if isinstance(response, grpc.RpcError):
                # If status code is in retryable status codes, sleep and continue/retry
                if self.status_for_retry and ErrorReportedByAgent(response).code in self.status_for_retry:
                    sleep_ms = randint(self.min_backoff, min(self.min_backoff * (try_i + 1), self.max_backoff))
                    sleep(sleep_ms / 1000)
                    continue
            break

        return response
