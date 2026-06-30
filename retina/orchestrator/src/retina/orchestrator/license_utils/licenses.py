#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Amarisoft License Client module for interacting with Amarisoft License Server.

This module provides a client implementation for the Amarisoft LTE License Server Remote API.
It handles authentication, command sending, and response parsing through a WebSocket interface.
"""

import asyncio
import hashlib
import hmac
import json
import uuid
from typing import Optional

import websockets


class LicenseClient:
    """
    Python client for the Amarisoft LTE License Server Remote API.
    - Performs handshake (HMAC-SHA256 authentication) if configured.
    - Allows sending any JSON command and receiving the response.
    """

    def __init__(self, host: str, port: int = 9006, password: Optional[str] = None, use_ssl: bool = False):
        """
        host:    IP or hostname of the License Server
        port:    Remote API port (default 9006)
        password: password if config uses com_auth
        use_ssl: True for wss:// (TLS), False for ws://
        """
        scheme = "wss" if use_ssl else "ws"
        self.uri = f"{scheme}://{host}:{port}"
        self.password = password

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    async def _handshake(self, ws):
        """Handles the initial greeting and HMAC authentication if required."""
        greeting = json.loads(await ws.recv())

        if greeting.get("message") == "authenticate":
            if not self.password:
                raise RuntimeError("The API requires a password, but none was provided.")
            challenge = greeting["challenge"]
            algo = greeting["type"]
            name = greeting["name"]
            data = f"{algo}:{self.password}:{name}".encode("utf-8")
            res = hmac.new(challenge.encode("utf-8"), data, hashlib.sha256).hexdigest()

            auth_req = {"message": "authenticate", "message_id": str(uuid.uuid4()), "res": res}
            await ws.send(json.dumps(auth_req))

            resp = json.loads(await ws.recv())
            if not resp.get("ready"):
                err = resp.get("error", "Authentication failed")
                raise RuntimeError(f"Auth error: {err}")

        elif greeting.get("message") != "ready":
            raise RuntimeError(f"Unexpected greeting: {greeting}")

    async def _send(self, payload: dict) -> dict:
        """Opens WS (with Origin), performs handshake, sends JSON payload and returns the response."""
        async with websockets.connect(self.uri, origin="http://10.12.1.174") as ws:  # pylint: disable=no-member
            await self._handshake(ws)
            await ws.send(json.dumps(payload))
            resp = await ws.recv()
            result: dict = json.loads(resp)
            return result

    def _run(self, coro):
        """Runs the coroutine in the event loop."""
        if self.loop.is_running():
            return asyncio.get_event_loop().run_until_complete(coro)
        return self.loop.run_until_complete(coro)

    def request(self, message: str, **params) -> dict:
        """
        Sends a generic command.
        message: name of the action (config_get, license, stats, reload, list, etc.)
        params:  extra parameters for that command.
        """
        payload = {"message": message, "message_id": str(uuid.uuid4())}
        payload.update(params)
        response: dict = self._run(self._send(payload))
        return response

    # Convenience methods
    def config_get(self) -> dict:
        """Get the current license server configuration."""
        return self.request("config_get")

    def get_license(self) -> dict:
        """Get the current license information."""
        return self.request("license")

    def stats(self) -> dict:
        """Get license server statistics."""
        return self.request("stats")

    def list_licenses(self) -> dict:
        """List all available licenses on the server."""
        return self.request("list")

    def reload(self) -> dict:
        """Reload the license server configuration."""
        return self.request("reload")

    def quit(self) -> dict:
        """Request the license server to quit."""
        return self.request("quit")

    def help(self) -> dict:
        """Get help information about available commands."""
        return self.request("help")

    def log_get(self, **opts) -> dict:
        """
        Get license server logs.

        Args:
            **opts: Options for log retrieval (e.g., lines, filter)
        """
        return self.request("log_get", **opts)

    def config_set(self, **cfg) -> dict:
        """
        Update the license server configuration.

        Args:
            **cfg: Configuration parameters to set
        """
        return self.request("config_set", logs=cfg)
