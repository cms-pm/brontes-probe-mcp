# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import pytest

import brontes_probe_mcp.core.session as session_module
from brontes_probe_mcp.core.broker import BrokerCore, SessionRequiredError
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import (
    BlackboxExportResult,
    ItmStreamHandle,
    ItmStreamSummary,
    LaneStatus,
    MemReadResult,
    ProbeState,
    ProgramResult,
    SessionStatus,
)


def _completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> CompletedProcess[str]:
    return CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture()
def mock_run() -> MagicMock:
    return MagicMock(return_value=_completed())


@pytest.fixture()
def mock_popen() -> MagicMock:
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 12345
    return MagicMock(return_value=proc)


@pytest.fixture()
def broker(mock_run: MagicMock, mock_popen: MagicMock, tmp_path: Path) -> BrokerCore:
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    return BrokerCore(
        config=config, _subprocess_run=mock_run, _subprocess_popen=mock_popen
    )


@pytest.fixture()
def broker_with_session(broker: BrokerCore) -> BrokerCore:
    broker._session_state = "healthy"
    return broker


# ── GDB-backed operations ─────────────────────────────────────────────────────

def test_halt_returns_probe_state(broker_with_session: BrokerCore) -> None:
    broker = broker_with_session
    result = broker.halt()
    assert isinstance(result, ProbeState)
    assert result.halted is True


def test_halt_calls_subprocess(
    broker_with_session: BrokerCore, mock_run: MagicMock
) -> None:
    broker_with_session.halt()
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert any("halt" in str(a) for a in args)


def test_resume_returns_probe_state(broker_with_session: BrokerCore) -> None:
    result = broker_with_session.resume()
    assert isinstance(result, ProbeState)
    assert result.resumed is True
    assert result.halted is False


def test_reset_soft_returns_probe_state(broker_with_session: BrokerCore) -> None:
    result = broker_with_session.reset(kind="soft")
    assert isinstance(result, ProbeState)
    assert result.reset is True


def test_reset_hard_returns_probe_state(broker_with_session: BrokerCore) -> None:
    result = broker_with_session.reset(kind="hard")
    assert isinstance(result, ProbeState)
    assert result.reset is True


def test_reset_halt_after(
    broker_with_session: BrokerCore, mock_run: MagicMock
) -> None:
    result = broker_with_session.reset(halt_after=True)
    assert result.halted_after is True
    args = mock_run.call_args[0][0]
    assert any("halt" in str(a) for a in args)


def test_mem_read_returns_result(broker_with_session: BrokerCore) -> None:
    result = broker_with_session.mem_read(addr=0x20000000, length=4)
    assert isinstance(result, MemReadResult)
    assert result.addr == 0x20000000
    assert result.length == 4


def test_mem_read_passes_address_to_gdb(
    broker_with_session: BrokerCore, mock_run: MagicMock
) -> None:
    broker_with_session.mem_read(addr=0x20000000, length=4)
    args = mock_run.call_args[0][0]
    assert any("20000000" in str(a) for a in args)


def test_program_returns_result(
    broker_with_session: BrokerCore, tmp_path: Path
) -> None:
    artifact = tmp_path / "firmware.elf"
    artifact.write_bytes(b"\x00" * 128)
    result = broker_with_session.program(artifact=artifact)
    assert isinstance(result, ProgramResult)
    assert result.format == "elf"
    assert result.programmed_bytes == 128


def test_blackbox_export_returns_result(
    broker_with_session: BrokerCore, mock_run: MagicMock, tmp_path: Path
) -> None:
    out = tmp_path / "export.bin"

    def _side_effect(*_args: object, **_kwargs: object) -> Any:
        out.write_bytes(b"\xde\xad" * 8)
        return _completed()

    mock_run.side_effect = _side_effect
    result = broker_with_session.blackbox_export(out=out)
    assert isinstance(result, BlackboxExportResult)
    assert result.bytes_written == 16


def test_blackbox_export_requires_session(broker: BrokerCore, tmp_path: Path) -> None:
    out = tmp_path / "export.bin"
    with pytest.raises(SessionRequiredError):
        broker.blackbox_export(out=out)


def test_blackbox_export_missing_file(
    broker_with_session: BrokerCore, tmp_path: Path
) -> None:
    out = tmp_path / "nonexistent.bin"
    result = broker_with_session.blackbox_export(out=out)
    assert result.bytes_written == 0


# ── FND-001: GDB error propagation ───────────────────────────────────────────

def test_gdb_failure_raises(
    broker_with_session: BrokerCore, mock_run: MagicMock
) -> None:
    mock_run.return_value = _completed(
        returncode=1, stderr="error: no debug probe detected"
    )
    with pytest.raises(RuntimeError, match="GDB exited 1"):
        broker_with_session.halt()


def test_gdb_failure_stderr_in_message(
    broker_with_session: BrokerCore, mock_run: MagicMock
) -> None:
    mock_run.return_value = _completed(returncode=1, stderr="Connection refused")
    with pytest.raises(RuntimeError, match="Connection refused"):
        broker_with_session.mem_read(addr=0x20000000, length=4)


# ── FND-002: session guard ────────────────────────────────────────────────────

def test_probe_op_without_session_raises(broker: BrokerCore) -> None:
    with pytest.raises(SessionRequiredError):
        broker.halt()


def test_all_probe_ops_require_session(broker: BrokerCore, tmp_path: Path) -> None:
    artifact = tmp_path / "fw.elf"
    artifact.write_bytes(b"\x00" * 16)
    probe_ops = [
        lambda: broker.halt(),
        lambda: broker.resume(),
        lambda: broker.reset(),
        lambda: broker.mem_read(addr=0x20000000, length=4),
        lambda: broker.program(artifact=artifact),
    ]
    for op in probe_ops:
        with pytest.raises(SessionRequiredError):
            op()


def test_session_state_tracks_start_stop(
    broker: BrokerCore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(broker._sessions, "_tcp_ready", lambda *a, **kw: True)

    assert broker._session_state == "stopped"
    broker.session_start(target="stm32g474")
    assert broker._session_state == "healthy"

    monkeypatch.setattr(session_module.os, "kill", lambda pid, sig: None)
    broker.session_stop()
    assert broker._session_state == "stopped"


# ── Lane / ITM operations ─────────────────────────────────────────────────────

def test_itm_stream_start_returns_handle(broker: BrokerCore) -> None:
    result = broker.itm_stream_start(ports=[0, 1])
    assert isinstance(result, ItmStreamHandle)
    assert result.ports == [0, 1]


def test_itm_stream_stop_returns_summary(broker: BrokerCore) -> None:
    broker.itm_stream_start(ports=[0])
    result = broker.itm_stream_stop()
    assert isinstance(result, ItmStreamSummary)
    assert result.stopped is True


def test_lane_status_returns_dict(broker: BrokerCore) -> None:
    result = broker.lane_status()
    assert isinstance(result, dict)
    assert "swd" in result
    assert "itm_swo" in result


def test_lane_release_returns_lane_status(broker: BrokerCore) -> None:
    result = broker.lane_release(lane="swd")
    assert isinstance(result, LaneStatus)
    assert result.lane == "swd"
    assert result.released is True


def test_lane_resume_returns_lane_status(broker: BrokerCore) -> None:
    result = broker.lane_resume(lane="swd")
    assert isinstance(result, LaneStatus)
    assert result.lane == "swd"
    assert result.resumed is True


# ── Session delegation ────────────────────────────────────────────────────────

def test_session_status_stopped_initially(broker: BrokerCore) -> None:
    result = broker.session_status()
    assert isinstance(result, SessionStatus)
    assert result.state == "stopped"


def test_session_start_returns_status(
    broker: BrokerCore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(broker._sessions, "_tcp_ready", lambda *a, **kw: True)
    result = broker.session_start(target="stm32g474", probe_uid="abc")
    assert isinstance(result, SessionStatus)
    assert result.state == "healthy"


def test_session_stop_returns_stopped(
    broker: BrokerCore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session_module.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(broker._sessions, "_tcp_ready", lambda *a, **kw: True)
    broker.session_start(target="stm32g474")

    monkeypatch.setattr(session_module.os, "kill", lambda pid, sig: None)
    result = broker.session_stop()
    assert isinstance(result, SessionStatus)
    assert result.state == "stopped"


# ── Audit log ─────────────────────────────────────────────────────────────────

def test_recent_lines_after_halt(broker_with_session: BrokerCore) -> None:
    broker_with_session.halt()
    lines = broker_with_session.recent_lines()
    assert len(lines) > 0
    assert any(line.method == "halt" for line in lines)


def test_recent_lines_after_multiple_ops(broker_with_session: BrokerCore) -> None:
    broker_with_session.halt()
    broker_with_session.resume()
    broker_with_session.reset()
    lines = broker_with_session.recent_lines()
    methods = [line.method for line in lines]
    assert "halt" in methods
    assert "resume" in methods
    assert "reset" in methods


def test_recent_lines_since_seq(broker_with_session: BrokerCore) -> None:
    broker_with_session.halt()
    broker_with_session.resume()
    all_lines = broker_with_session.recent_lines()
    assert len(all_lines) >= 2
    first_seq = all_lines[0].seq
    lines_after = broker_with_session.recent_lines(since_seq=first_seq + 1)
    assert all(entry.seq >= first_seq + 1 for entry in lines_after)


def test_recent_lines_limit(broker_with_session: BrokerCore) -> None:
    for _ in range(10):
        broker_with_session.halt()
    lines = broker_with_session.recent_lines(limit=3)
    assert len(lines) <= 3


def test_recent_lines_seq_monotonic(broker_with_session: BrokerCore) -> None:
    broker_with_session.halt()
    broker_with_session.resume()
    broker_with_session.reset()
    lines = broker_with_session.recent_lines()
    seqs = [entry.seq for entry in lines]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_audit_lane_field_set(broker: BrokerCore) -> None:
    broker.itm_stream_start(ports=[0])
    lines = broker.recent_lines()
    itm_lines = [entry for entry in lines if entry.method == "itm_stream_start"]
    assert len(itm_lines) == 1
    assert itm_lines[0].lane == "itm_swo"


# ── COM-003: mem_read output parsing ─────────────────────────────────────────

def test_mem_read_format_hex(
    broker_with_session: BrokerCore, mock_run: MagicMock
) -> None:
    mock_run.return_value = _completed(
        stdout="0x20000000:\t0xDEADBEEF\t0x00000001\n"
    )
    result = broker_with_session.mem_read(addr=0x20000000, length=8, format="hex")
    assert result.format == "hex"
    assert isinstance(result.value, list)
    assert result.value == ["0xDEADBEEF", "0x00000001"]


def test_mem_read_format_bytes_default(
    broker_with_session: BrokerCore, mock_run: MagicMock
) -> None:
    import base64

    mock_run.return_value = _completed(
        stdout="0x20000000:\t0xDEADBEEF\n"
    )
    result = broker_with_session.mem_read(addr=0x20000000, length=4)
    assert result.format == "bytes"
    assert isinstance(result.value, str)
    # 0xDEADBEEF little-endian = EF BE AD DE
    expected = base64.b64encode(bytes([0xEF, 0xBE, 0xAD, 0xDE])).decode()
    assert result.value == expected


def test_program_bytes_from_gdb_load_output(
    broker_with_session: BrokerCore, mock_run: MagicMock, tmp_path: Path
) -> None:
    mock_run.return_value = _completed(
        stdout=(
            "Loading section .text, size 0x1234 lma 0x08000000\n"
            "Start address 0x08000000, load size 4660\n"
            "Transfer rate: 37 KB/sec, 1553 bytes/write.\n"
        )
    )
    elf = tmp_path / "fw.elf"
    elf.write_bytes(b"\x00" * 64)
    result = broker_with_session.program(artifact=elf)
    assert result.programmed_bytes == 4660


# ── COM-007: blackbox_export uses GDB dump binary memory ─────────────────────

def test_blackbox_export_calls_gdb_dump(
    broker_with_session: BrokerCore, mock_run: MagicMock, tmp_path: Path
) -> None:
    out = tmp_path / "snap.bin"

    def _side_effect(*args: object, **_kwargs: object) -> Any:
        out.write_bytes(b"\x00" * 512 * 1024)
        return _completed()

    mock_run.side_effect = _side_effect
    result = broker_with_session.blackbox_export(out=out)
    assert result.bytes_written > 0
    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert any("dump binary memory" in str(a) for a in cmd)
    assert any("08000000" in str(a) for a in cmd)


# ── COM-004: lane thread-safety ───────────────────────────────────────────────

def test_lane_supervisor_concurrent_mutations(broker: BrokerCore) -> None:
    import threading as _threading

    errors: list[Exception] = []

    def _toggle(lane: str, n: int) -> None:
        for i in range(n):
            try:
                if i % 2 == 0:
                    broker.lane_release(lane=lane)
                else:
                    broker.lane_resume(lane=lane)
            except Exception as exc:
                errors.append(exc)

    threads = [
        _threading.Thread(target=_toggle, args=("swd", 50)),
        _threading.Thread(target=_toggle, args=("swd", 50)),
        _threading.Thread(target=_toggle, args=("itm_swo", 50)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [], f"Thread errors: {errors}"
