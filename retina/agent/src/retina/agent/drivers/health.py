#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Retina custom logic on top of the health checking protocol for gRPC
"""

import logging
import signal
from datetime import datetime
from threading import Event, Thread

import grpc
from grpc_health.v1.health import HealthServicer
from grpc_health.v1.health_pb2 import HealthCheckRequest, HealthCheckResponse


class RetinaHealth(HealthServicer):
    """
    Retina custom logic on top of the health checking protocol for gRPC
    """

    _CHECK_STEP: float = 0.5

    def __init__(self, keep_alive_timeout: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keep_alive_timeout = keep_alive_timeout
        self._last_keep_alive_date: datetime = datetime.now()
        self._alive_thread: Thread = Thread(target=self._still_alive)
        self._alive_event: Event = Event()
        self._alive_thread.start()

    def Check(self, request: HealthCheckRequest, context: grpc.RpcContext) -> HealthCheckResponse:
        with self._lock:
            self._last_keep_alive_date = datetime.now()
        return super().Check(request, context)

    def enter_graceful_shutdown(self):
        self._alive_event.set()
        self._alive_thread.join()
        return super().enter_graceful_shutdown()

    def _still_alive(self):
        while not self._alive_event.is_set():
            with self._lock:
                time_since_last_keep_alive = datetime.now() - self._last_keep_alive_date
            if time_since_last_keep_alive.seconds >= self._keep_alive_timeout:
                logging.error(
                    "%s seconds since last keep alive received!",
                    time_since_last_keep_alive.seconds,
                )
                self._alive_event.set()
                signal.raise_signal(signal.SIGINT)
            else:
                self._alive_event.wait(self._CHECK_STEP)
