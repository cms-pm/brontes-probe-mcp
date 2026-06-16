# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.3 H7 — quiet shutdown on BrokenPipe.

Acceptance: SCN-2.1.3-SOCKET-QUIET-DISCONNECT, SCN-2.1.3-TCP-QUIET-DISCONNECT,
SCN-2.1.3-DEBUG-LOG-PRESENT.
"""
from __future__ import annotations

import json
import logging
import socket
import struct
import subprocess
import tempfile
import threading
import time
from io import BytesIO
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports.socket import _RequestHandler, _UnixServer
from brontes_probe_mcp.transports.tcp import _TcpRequestHandler


def _completed(stdout: str = "", returncode: int = 0) -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@pytest.fixture()
def broker(tmp_path: Path) -> BrokerCore:
    b = BrokerCore(
        config=BrokerConfig(log_dir=str(tmp_path / "logs")),
        _subprocess_run=MagicMock(return_value=_completed()),
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )
    b._session_state = "healthy"
    return b


# ── direct handler unit tests ────────────────────────────────────────────────


class _FakeWriteFile:
    """Mimic a peer hangup: raise BrokenPipeError after N successful writes.

    ``raise_after_n_writes=0`` raises on the first ``write()`` call;
    ``=1`` accepts one write then raises on the second; etc.
    """

    def __init__(self, raise_after_n_writes: int = 0) -> None:
        self._writes = 0
        self._raise_after = raise_after_n_writes
        self.flushed = 0
        self.written: list[bytes] = []

    def write(self, data: bytes) -> int:
        if self._writes >= self._raise_after:
            raise BrokenPipeError(32, "Broken pipe")
        self._writes += 1
        self.written.append(data)
        return len(data)

    def flush(self) -> None:
        self.flushed += 1


def _make_socket_handler(
    broker: BrokerCore, rfile: BytesIO, wfile: Any
) -> _RequestHandler:
    handler = _RequestHandler.__new__(_RequestHandler)
    handler.server = MagicMock()
    handler.server.broker = broker
    handler.rfile = rfile  # type: ignore[assignment]
    handler.wfile = wfile  # type: ignore[assignment]
    handler.connection = MagicMock()
    handler.connection.getsockopt = MagicMock(side_effect=OSError)
    return handler


def test_socket_handler_swallows_brokenpipe_on_write(
    broker: BrokerCore, caplog: pytest.LogCaptureFixture
) -> None:
    rfile = BytesIO(b'{"method":"halt","kwargs":{}}\n')
    wfile = _FakeWriteFile(raise_after_n_writes=0)
    handler = _make_socket_handler(broker, rfile, wfile)
    with caplog.at_level(logging.DEBUG, logger="brontes_probe_mcp.transports.socket"):
        handler.handle()  # must not raise
    assert any(
        "socket client disconnected" in r.message and r.levelno == logging.DEBUG
        for r in caplog.records
    )


def test_socket_handler_swallows_connectionreset(broker: BrokerCore) -> None:
    class _ResetReader:
        def __iter__(self) -> Any:
            return self

        def __next__(self) -> bytes:
            raise ConnectionResetError(104, "Connection reset by peer")

    handler = _make_socket_handler(broker, _ResetReader(), _FakeWriteFile())  # type: ignore[arg-type]
    handler.handle()  # must not raise


def test_tcp_handler_swallows_brokenpipe(
    broker: BrokerCore, caplog: pytest.LogCaptureFixture
) -> None:
    rfile = BytesIO(b"tok\n" + b'{"method":"halt","kwargs":{}}\n')
    wfile = _FakeWriteFile(raise_after_n_writes=0)
    handler = _TcpRequestHandler.__new__(_TcpRequestHandler)
    handler.server = MagicMock()
    handler.server.broker = broker
    handler.server.token = "tok"
    handler.rfile = rfile  # type: ignore[assignment]
    handler.wfile = wfile  # type: ignore[assignment]
    with caplog.at_level(logging.DEBUG, logger="brontes_probe_mcp.transports.tcp"):
        handler.handle()  # must not raise
    assert any(
        "tcp client disconnected" in r.message and r.levelno == logging.DEBUG
        for r in caplog.records
    )


# ── integration: server survives a real RST mid-RPC ──────────────────────────


@pytest.fixture()
def unix_server_running(broker: BrokerCore) -> Any:
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        sock_path = str(Path(td) / "p.sock")
        config = BrokerConfig(socket_path=sock_path)
        srv = _UnixServer(broker, config)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        yield sock_path
        srv.shutdown()
        t.join(timeout=2)


def _force_rst_close(s: socket.socket) -> None:
    """SO_LINGER {on=1, t=0} forces an RST instead of a graceful FIN."""
    linger = struct.pack("ii", 1, 0)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
    s.close()


def test_unix_server_survives_client_rst(unix_server_running: str) -> None:
    sock_path = unix_server_running
    # Fire and forcibly reset before reading any reply.
    for _ in range(3):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sock_path)
        s.sendall(b'{"method":"halt","kwargs":{}}\n')
        _force_rst_close(s)
    # 0.5s gives the threadpool comfortable room under CI load —
    # RSTs are cheap, so the wall-time cost is invisible.
    time.sleep(0.5)
    # Server still serves new connections.
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(sock_path)
    s.sendall(b'{"method":"lane_status","kwargs":{}}\n')
    reply = b""
    while not reply.endswith(b"\n"):
        chunk = s.recv(4096)
        if not chunk:
            break
        reply += chunk
    s.close()
    parsed: dict[str, Any] = json.loads(reply.strip())
    assert isinstance(parsed, dict)
