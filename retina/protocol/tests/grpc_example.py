#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

import unittest
from concurrent.futures import ThreadPoolExecutor

import grpc

from retina.protocol.base_pb2 import Success
from retina.protocol.ue_pb2 import UEStartInfo
from retina.protocol.ue_pb2_grpc import add_UEServicer_to_server, UEServicer, UEStub


class UEServer(UEServicer):
    def Start(self, request, context):
        print(f"[SERVER] received start {request}")
        return Success(value=True)


class ExampleTestCase(unittest.TestCase):
    SERVER_PORT: int = 50051

    @classmethod
    def start_ue_server(cls) -> UEServer:
        server = grpc.server(ThreadPoolExecutor(max_workers=10))
        add_UEServicer_to_server(UEServer(), server)
        server.add_insecure_port(f"[::]:{cls.SERVER_PORT}")
        server.start()
        print("[SERVER] Started")
        return server

    def test_basic_grpc(self):
        server = self.start_ue_server()
        with grpc.insecure_channel(f"localhost:{self.SERVER_PORT}") as channel:
            stub = UEStub(channel)
            print("[CLIENT] sending start")
            response = stub.Start(UEStartInfo())
            print(f"[CLIENT] response {response.value}")
        server.stop(1).wait()


if __name__ == "__main__":
    unittest.main()
