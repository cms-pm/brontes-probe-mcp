# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import signal
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import brontes_probe_mcp.core.session as session_module
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.session import SessionManager


@pytest.fixture()
def config(tmp_path: Path) -> BrokerConfig:
    return BrokerConfig(log_dir=str(tmp_path / "logs"))


@pytest.fixture()
def mock_proc() -> MagicMock:
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 12345
    return proc


@pytest.fixture()
def mock_popen(mock_proc: MagicMock) -> MagicMock:
    return MagicMock(return_value=mock_proc)


@pytest.fixture()
def manager(config: BrokerConfig, mock_popen: MagicMock) -> SessionManager:
    return SessionManager(config=config, _popen=mock_popen)


def test_start_stop_cycle(
    manager: SessionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)

    status = manager.start(target="stm32g474", probe_uid="abc123")
    assert status.state == "healthy"
    assert status.target == "stm32g474"
    assert status.probe_uid == "abc123"

    monkeypatch.setattr(session_module.os, "kill", lambda pid, sig: None)
    stopped = manager.stop()
    assert stopped.state == "stopped"


def test_start_returns_unhealthy_on_tcp_timeout(
    manager: SessionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: False)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)

    status = manager.start(target="stm32g474")
    assert status.state == "unhealthy"


def test_status_stopped_when_no_meta(config: BrokerConfig) -> None:
    mgr = SessionManager(config=config)
    status = mgr.status()
    assert status.state == "stopped"


def test_status_healthy(
    manager: SessionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(manager, "_probe_tcp", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(session_module.os, "kill", lambda pid, sig: None)

    manager.start(target="stm32g474")
    status = manager.status()
    assert status.state == "healthy"


def test_status_stale(config: BrokerConfig) -> None:
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "pid": 99999999,
        "gdb_host": "127.0.0.1",
        "gdb_port": 3333,
        "target": "test",
        "probe_uid": None,
    }
    (log_dir / "test.json").write_text(json.dumps(meta))
    mgr = SessionManager(config=config)
    status = mgr.status()
    # PID 99999999 won't exist; TCP also fails → stale or unhealthy
    assert status.state in ("stale", "unhealthy")


def test_stop_force_sends_sigkill(
    manager: SessionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)
    manager.start(target="stm32g474")

    kill_calls: list[tuple[int, int]] = []

    def _mock_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    monkeypatch.setattr(session_module.os, "kill", _mock_kill)
    stopped = manager.stop(force=True)
    assert stopped.state == "stopped"
    assert any(sig == signal.SIGKILL for _, sig in kill_calls)


def test_operation_lock_prevents_concurrent_start(
    config: BrokerConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    lock_path = log_dir / ".lock.json"
    lock_path.write_text("{}")

    mgr = SessionManager(config=config)
    monkeypatch.setattr(mgr, "_tcp_ready", lambda *a, **kw: True)

    with pytest.raises(RuntimeError, match="lock held"):
        mgr.start(target="stm32g474")

    lock_path.unlink()


def test_start_passes_probe_uid_to_gdbserver(
    manager: SessionManager,
    mock_popen: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)

    manager.start(target="stm32g474", probe_uid="deadbeef")
    call_args = mock_popen.call_args[0][0]
    assert "--uid" in call_args
    assert "deadbeef" in call_args


def test_start_passes_frequency_to_gdbserver(
    manager: SessionManager,
    mock_popen: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)

    manager.start(target="stm32g474", frequency_hz=4_000_000)
    call_args = mock_popen.call_args[0][0]
    assert "--frequency" in call_args


def test_stop_no_meta_returns_stopped(config: BrokerConfig) -> None:
    mgr = SessionManager(config=config)
    result = mgr.stop()
    assert result.state == "stopped"


def test_status_protocol_version(config: BrokerConfig) -> None:
    mgr = SessionManager(config=config)
    status = mgr.status()
    assert status.protocol_version == "1.1"
