# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import signal
import subprocess
import time
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
    # Single-session profile is always "default.json"
    (log_dir / "default.json").write_text(json.dumps(meta))
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

    killpg_calls: list[tuple[int, int]] = []

    def _mock_killpg(pgid: int, sig: int) -> None:
        killpg_calls.append((pgid, sig))

    monkeypatch.setattr(session_module.os, "killpg", _mock_killpg)
    stopped = manager.stop(force=True)
    assert stopped.state == "stopped"
    assert any(sig == signal.SIGKILL for _, sig in killpg_calls)


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


# ── COM-005: session_stop uses os.killpg ─────────────────────────────────────

def test_stop_uses_killpg(
    manager: SessionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)
    manager.start(target="stm32g474")

    killpg_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        session_module.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig))
    )
    manager.stop()
    assert len(killpg_calls) > 0


def test_session_stop_kills_process_group(
    manager: SessionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid + 1000)
    manager.start(target="stm32g474")

    meta = manager._read_meta()
    assert meta is not None
    recorded_pgid = meta.get("process_group_id")

    killpg_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        session_module.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig))
    )
    manager.stop()
    assert any(pgid == recorded_pgid for pgid, _ in killpg_calls)


# ── COM-006: stale lock auto-recovery ────────────────────────────────────────

def test_stale_lock_auto_recovered(
    manager: SessionManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_dir = Path(manager._config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    lock_path = log_dir / ".lock.json"
    lock_path.write_text("{}")

    # Back-date mtime past the stale threshold
    old_time = time.time() - 120
    import os as _os

    _os.utime(str(lock_path), (old_time, old_time))

    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)
    result = manager.start(target="stm32g474")
    assert result.state == "healthy"
    assert not lock_path.exists()


# ── COM-009: single-session implicit replace ──────────────────────────────────

def test_session_start_replaces_active_session(
    manager: SessionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(manager, "_tcp_ready", lambda *a, **kw: True)
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)

    manager.start(target="stm32g474")

    killpg_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        session_module.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig))
    )
    result = manager.start(target="nrf52840")
    assert result.state == "healthy"
    assert result.target == "nrf52840"
    # Old session was killed before new one started
    assert len(killpg_calls) > 0
    meta2 = manager._read_meta()
    assert meta2 is not None
    assert meta2.get("target") == "nrf52840"


def test_session_status_uses_default_profile(
    config: BrokerConfig, tmp_path: Path
) -> None:
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    # Write a non-default profile (old format) — should NOT be picked up
    (log_dir / "stm32g474.json").write_text(
        '{"pid": 1, "gdb_host": "127.0.0.1", "gdb_port": 3333, "target": "stm32g474"}'
    )
    mgr = SessionManager(config=config)
    # With single-session semantics, status reads "default.json" only
    status = mgr.status()
    assert status.state == "stopped"
