# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import socket
import subprocess
import threading
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports import tcp as tcp_transport
from brontes_probe_mcp.transports.tcp import _TcpServer


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


_TEST_TOKEN = "test-bearer-token-xyz"


@pytest.fixture()
def tcp_server(broker_instance: BrokerCore) -> Any:
    # Use ephemeral port
    config = BrokerConfig(tcp_host="127.0.0.1", tcp_port=0, token=_TEST_TOKEN)
    srv = _TcpServer(broker_instance, config, _TEST_TOKEN)
    # Get the actual assigned port
    port: int = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv, port
    srv.shutdown()
    t.join(timeout=2)


def _call(
    port: int,
    token: str,
    method: str,
    kwargs: dict[str, Any] | None = None,
) -> Any:
    """Connect to TCP server, authenticate, send request, return parsed JSON."""
    payload = json.dumps({"method": method, "kwargs": kwargs or {}})
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as s:
        sf = s.makefile("rwb")
        sf.write((token + "\n").encode())
        sf.flush()
        sf.write((payload + "\n").encode())
        sf.flush()
        response = sf.readline()
    return json.loads(response.strip())


def test_no_token_raises(tmp_path: Path) -> None:
    config = BrokerConfig(token=None, token_file=None, log_dir=str(tmp_path / "logs"))
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 1
    broker = BrokerCore(
        config=config,
        _subprocess_run=MagicMock(return_value=_completed()),
        _subprocess_popen=MagicMock(return_value=proc),
    )
    with pytest.raises(RuntimeError, match="bearer token"):
        tcp_transport.run(broker, config)


def test_halt_via_tcp(tcp_server: Any) -> None:
    srv, port = tcp_server
    result = _call(port, _TEST_TOKEN, "halt")
    assert result.get("halted") is True


def test_wrong_token_gets_no_response(tcp_server: Any) -> None:
    srv, port = tcp_server
    response = b""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5.0) as s:
            sf = s.makefile("rwb")
            sf.write(b"bad-token\n")
            sf.flush()
            sf.write(b'{"method": "halt", "kwargs": {}}\n')
            sf.flush()
            # Server closes connection without sending a response
            response = sf.readline()
    except ConnectionResetError:
        # macOS: server closes => ConnectionResetError on read; no response = correct
        response = b""
    assert response == b""


def test_flash_alias_tcp(tcp_server: Any, tmp_path: Path) -> None:
    srv, port = tcp_server
    artifact = tmp_path / "fw.elf"
    artifact.write_bytes(b"\x00" * 64)
    result = _call(port, _TEST_TOKEN, "flash", {"artifact": str(artifact)})
    assert "programmed_bytes" in result


def test_recent_lines_wrapper_tcp(tcp_server: Any) -> None:
    srv, port = tcp_server
    result = _call(port, _TEST_TOKEN, "recent_lines")
    assert "next_seq" in result
    assert "lines" in result


# ── COM-008c: tcp_allow_remote enforcement ────────────────────────────────────

def test_tcp_allow_remote_false_rejects_non_loopback(tmp_path: Path) -> None:
    from brontes_probe_mcp.__main__ import serve_all

    config = BrokerConfig(
        token="tok",
        tcp_host="0.0.0.0",
        tcp_allow_remote=False,
        log_dir=str(tmp_path / "logs"),
        transports=["tcp"],
    )
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 1
    broker = BrokerCore(
        config=config,
        _subprocess_run=MagicMock(return_value=_completed()),
        _subprocess_popen=MagicMock(return_value=proc),
    )
    with pytest.raises(RuntimeError, match="tcp_allow_remote"):
        serve_all(config, broker)


def test_tcp_allow_remote_true_permits_non_loopback(tmp_path: Path) -> None:
    from brontes_probe_mcp.__main__ import serve_all

    config = BrokerConfig(
        token="tok",
        tcp_host="0.0.0.0",
        tcp_allow_remote=True,
        log_dir=str(tmp_path / "logs"),
        transports=["tcp"],
    )
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 1
    broker = BrokerCore(
        config=config,
        _subprocess_run=MagicMock(return_value=_completed()),
        _subprocess_popen=MagicMock(return_value=proc),
    )
    # Should not raise; the thread starts but we don't join
    import threading

    t = threading.Thread(target=serve_all, args=(config, broker), daemon=True)
    t.start()
    t.join(timeout=0.5)  # let it start and bind, then daemon exit cleans up
