# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.cli import main
from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports.socket import _UnixServer


def _completed(stdout: str = "", returncode: int = 0) -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@pytest.fixture()
def live_broker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BrokerCore:
    mock_run = MagicMock(return_value=_completed())
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 12345
    mock_popen = MagicMock(return_value=proc)
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    broker = BrokerCore(
        config=config,
        _subprocess_run=mock_run,
        _subprocess_popen=mock_popen,
    )
    monkeypatch.setattr(broker._sessions, "_tcp_ready", lambda *a, **kw: False)
    broker._session_state = "healthy"
    return broker


@pytest.fixture()
def live_socket(live_broker: BrokerCore) -> Any:
    # Use /tmp directly to stay under macOS AF_UNIX 104-char path limit
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        sock_path = str(Path(td) / "p.sock")
        config = BrokerConfig(socket_path=sock_path)
        srv = _UnixServer(live_broker, config)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        yield sock_path
        srv.shutdown()
        t.join(timeout=2)


def test_call_session_status(
    live_socket: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sys.argv = [
        "brontes-probe-mcp-cli", "call", "session_status",
        "--socket", live_socket,
    ]
    main()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert isinstance(payload, dict)
    assert "state" in payload
    assert "error" not in payload


def test_call_with_json_kwargs(
    live_socket: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sys.argv = [
        "brontes-probe-mcp-cli", "call", "mem_read",
        "--json", '{"addr": 536870912, "length": 4}',
        "--socket", live_socket,
    ]
    main()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload.get("length") == 4


def test_call_invalid_json_exits_2(
    live_socket: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sys.argv = [
        "brontes-probe-mcp-cli", "call", "session_status",
        "--json", "not-json",
        "--socket", live_socket,
    ]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "Invalid --json" in capsys.readouterr().err


def test_call_non_object_json_exits_2(
    live_socket: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sys.argv = [
        "brontes-probe-mcp-cli", "call", "session_status",
        "--json", "[1,2,3]",
        "--socket", live_socket,
    ]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_call_missing_socket_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sys.argv = [
        "brontes-probe-mcp-cli", "call", "session_status",
        "--socket", str(tmp_path / "nonexistent.sock"),
    ]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "call failed" in capsys.readouterr().err


def test_call_timeout_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    """A socket that accepts but never replies should hit settimeout → exit 1."""
    import socket as _sock

    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        sock_path = str(Path(td) / "silent.sock")
        srv = _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM)
        srv.bind(sock_path)
        srv.listen(1)

        accepted: list[Any] = []

        def _accept_and_hold() -> None:
            conn, _ = srv.accept()
            accepted.append(conn)  # keep alive; never write back

        t = threading.Thread(target=_accept_and_hold, daemon=True)
        t.start()
        try:
            sys.argv = [
                "brontes-probe-mcp-cli", "call", "session_status",
                "--socket", sock_path, "--timeout", "0.2",
            ]
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
            assert "call failed" in capsys.readouterr().err
        finally:
            for c in accepted:
                c.close()
            srv.close()
            t.join(timeout=1)


def test_call_truncated_reply_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    """Server closes without a trailing newline → empty/truncated reply → exit 1."""
    import socket as _sock

    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        sock_path = str(Path(td) / "truncated.sock")
        srv = _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM)
        srv.bind(sock_path)
        srv.listen(1)

        def _accept_and_close() -> None:
            conn, _ = srv.accept()
            conn.close()  # no reply at all → empty buf

        t = threading.Thread(target=_accept_and_close, daemon=True)
        t.start()
        try:
            sys.argv = [
                "brontes-probe-mcp-cli", "call", "session_status",
                "--socket", sock_path, "--timeout", "2.0",
            ]
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
            assert "empty reply" in capsys.readouterr().err
        finally:
            srv.close()
            t.join(timeout=1)


def test_call_unknown_method_returns_error_exits_1(
    live_socket: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sys.argv = [
        "brontes-probe-mcp-cli", "call", "no_such_method",
        "--socket", live_socket,
    ]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert "error" in payload
