# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import logging
import socketserver
from pathlib import Path
from typing import Any

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports import _rpc

_log = logging.getLogger(__name__)


def _resolve_token(config: BrokerConfig) -> str | None:
    """Return bearer token from config or token_file, or None."""
    if config.token:
        return config.token
    if config.token_file:
        try:
            return Path(config.token_file).read_text().strip()
        except OSError:
            return None
    return None


class _TcpRequestHandler(socketserver.StreamRequestHandler):
    server: _TcpServer  # noqa: RUF012

    def handle(self) -> None:
        # First line is bearer token
        raw_token = self.rfile.readline()
        if not raw_token:
            return
        bearer = raw_token.strip().decode(errors="replace")
        if bearer != self.server.token:
            return

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
                    response = _rpc.error_response("method_unknown", str(exc), {})
                except Exception as exc:
                    response = _rpc.error_response(
                        "broker_internal_error", str(exc), {}
                    )
                self.wfile.write((response + "\n").encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError) as exc:
            # Client went away mid-RPC; quiet by design — see socket.py.
            _log.debug("tcp client disconnected: %s", exc)
            return


class _TcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(
        self,
        broker: BrokerCore,
        config: BrokerConfig,
        token: str,
    ) -> None:
        self.broker = broker
        self.token = token
        super().__init__((config.tcp_host, config.tcp_port), _TcpRequestHandler)


def run(broker: BrokerCore, config: BrokerConfig) -> None:
    """Start the loopback TCP JSON-RPC server (blocking).

    Raises RuntimeError if no bearer token is configured.
    """
    token = _resolve_token(config)
    if token is None:
        raise RuntimeError(
            "TCP transport requires a bearer token; "
            "set PROBE_BROKER_TOKEN or PROBE_BROKER_TOKEN_FILE"
        )
    with _TcpServer(broker, config, token) as srv:
        srv.serve_forever()
