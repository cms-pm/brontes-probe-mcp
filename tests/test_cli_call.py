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
