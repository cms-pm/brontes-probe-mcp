# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import threading
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports.socket import _UnixServer


def _completed(stdout: str = "", returncode: int = 0) -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@pytest.fixture()
def mock_run() -> MagicMock:
    return MagicMock(return_value=_completed())


@pytest.fixture()
def mock_popen() -> MagicMock:
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 12345
    return MagicMock(return_value=proc)


@pytest.fixture()
def broker_instance(
    mock_run: MagicMock, mock_popen: MagicMock, tmp_path: Path
) -> BrokerCore:
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    b = BrokerCore(
        config=config, _subprocess_run=mock_run, _subprocess_popen=mock_popen
    )
    b._session_state = "healthy"
    return b


@pytest.fixture()
def unix_server(broker_instance: BrokerCore) -> Any:
    # Use /tmp directly to stay under macOS AF_UNIX 104-char path limit
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        sock_path = str(Path(td) / "p.sock")
        config = BrokerConfig(socket_path=sock_path)
        srv = _UnixServer(broker_instance, config)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        yield srv, sock_path
        srv.shutdown()
        t.join(timeout=2)


def _call(sock_path: str, method: str, kwargs: dict[str, Any] | None = None) -> Any:
    """Connect to Unix socket, send JSON line, read response."""
    payload = json.dumps({"method": method, "kwargs": kwargs or {}})
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(5.0)
        s.connect(sock_path)
        s.sendall((payload + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    return json.loads(data.strip())


def test_halt_via_socket(unix_server: Any) -> None:
    _srv, sock_path = unix_server
    result = _call(sock_path, "halt")
    assert result.get("halted") is True


def test_flash_alias(unix_server: Any, tmp_path: Path) -> None:
    _srv, sock_path = unix_server
    artifact = tmp_path / "fw.elf"
    artifact.write_bytes(b"\x00" * 64)
    result = _call(sock_path, "flash", {"artifact": str(artifact)})
    assert "programmed_bytes" in result


def test_unknown_method_returns_error(unix_server: Any) -> None:
    _srv, sock_path = unix_server
    result = _call(sock_path, "no_such_method")
    assert "error" in result


def test_recent_lines_has_next_seq(unix_server: Any) -> None:
    _srv, sock_path = unix_server
    result = _call(sock_path, "recent_lines")
    assert "next_seq" in result
    assert "lines" in result


def test_lane_status_returns_dict(unix_server: Any) -> None:
    _srv, sock_path = unix_server
    result = _call(sock_path, "lane_status")
    assert isinstance(result, dict)
    assert "swd" in result or "itm_swo" in result


def test_mem_read_returns_value(unix_server: Any) -> None:
    _srv, sock_path = unix_server
    result = _call(sock_path, "mem_read", {"addr": 0x20000000, "length": 4})
    assert "value" in result
