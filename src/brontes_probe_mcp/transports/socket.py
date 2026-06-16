# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import logging
import os
import socket as socket_module
import socketserver
from pathlib import Path
from typing import Any

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports import _rpc

_log = logging.getLogger(__name__)


class _RequestHandler(socketserver.StreamRequestHandler):
    server: _UnixServer  # noqa: RUF012

    def handle(self) -> None:
        so_peercred = getattr(socket_module, "SO_PEERCRED", None)
        if so_peercred is not None:
            try:
                cred = self.connection.getsockopt(
                    socket_module.SOL_SOCKET, so_peercred, 12
                )
                uid = int.from_bytes(cred[4:8], "little")
                if uid != os.getuid():
                    return
            except OSError:
                pass

        try:
            for raw_line in self.rfile:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload: dict[str, Any] = json.loads(line)
                    method: str = str(payload.get("method", ""))
                    kwargs: dict[str, Any] = dict(payload.get("kwargs", {}))
                    result = _rpc.dispatch(self.server.broker, method, kwargs)
                    response = _rpc.serialize(result)
                except KeyError as exc:
                    response = _rpc.error_response(
                        "method_unknown", str(exc), {}
                    )
                except Exception as exc:
                    response = _rpc.error_response(
                        "broker_internal_error", str(exc), {}
                    )
                self.wfile.write((response + "\n").encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError) as exc:
            # Client went away mid-RPC. Common during graceful shutdown:
            # the peer closes its read side before the broker can write
            # back. Logged at DEBUG to avoid alarming output that survived
            # 0.2.2 retrospectives.
            _log.debug("socket client disconnected: %s", exc)
            return


class _UnixServer(socketserver.ThreadingUnixStreamServer):
    def __init__(self, broker: BrokerCore, config: BrokerConfig) -> None:
        socket_path = config.socket_path
        Path(socket_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass
        self.broker = broker
        super().__init__(socket_path, _RequestHandler)


def run(broker: BrokerCore, config: BrokerConfig) -> None:
    """Start the Unix-domain socket JSON-RPC server (blocking)."""
    with _UnixServer(broker, config) as srv:
        srv.serve_forever()
