# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest

import brontes_probe_mcp.core.session as session_module
from brontes_probe_mcp.core.broker import BrokerCore
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
def broker(mock_run: MagicMock, mock_popen: MagicMock, tmp_path: Path) -> BrokerCore:
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    return BrokerCore(
        config=config, _subprocess_run=mock_run, _subprocess_popen=mock_popen
    )


# ── GDB-backed operations ─────────────────────────────────────────────────────

def test_halt_returns_probe_state(broker: BrokerCore) -> None:
    result = broker.halt()
    assert isinstance(result, ProbeState)
    assert result.halted is True


def test_halt_calls_subprocess(broker: BrokerCore, mock_run: MagicMock) -> None:
    broker.halt()
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert any("halt" in str(a) for a in args)


def test_resume_returns_probe_state(broker: BrokerCore) -> None:
    result = broker.resume()
    assert isinstance(result, ProbeState)
    assert result.resumed is True
    assert result.halted is False


def test_reset_soft_returns_probe_state(broker: BrokerCore) -> None:
    result = broker.reset(kind="soft")
    assert isinstance(result, ProbeState)
    assert result.reset is True


def test_reset_hard_returns_probe_state(broker: BrokerCore) -> None:
    result = broker.reset(kind="hard")
    assert isinstance(result, ProbeState)
    assert result.reset is True


def test_reset_halt_after(broker: BrokerCore, mock_run: MagicMock) -> None:
    result = broker.reset(halt_after=True)
    assert result.halted_after is True
    args = mock_run.call_args[0][0]
    assert any("halt" in str(a) for a in args)


def test_mem_read_returns_result(broker: BrokerCore) -> None:
    result = broker.mem_read(addr=0x20000000, length=4)
    assert isinstance(result, MemReadResult)
    assert result.addr == 0x20000000
    assert result.length == 4


def test_mem_read_passes_address_to_gdb(
    broker: BrokerCore, mock_run: MagicMock
) -> None:
    broker.mem_read(addr=0x20000000, length=4)
    args = mock_run.call_args[0][0]
    assert any("20000000" in str(a) for a in args)


def test_program_returns_result(broker: BrokerCore, tmp_path: Path) -> None:
    artifact = tmp_path / "firmware.elf"
    artifact.write_bytes(b"\x00" * 128)
    result = broker.program(artifact=artifact)
    assert isinstance(result, ProgramResult)
    assert result.format == "elf"
    assert result.programmed_bytes == 128


def test_blackbox_export_returns_result(broker: BrokerCore, tmp_path: Path) -> None:
    out = tmp_path / "export.bin"
    out.write_bytes(b"\xde\xad" * 8)
    result = broker.blackbox_export(out=out)
    assert isinstance(result, BlackboxExportResult)
    assert result.bytes_written == 16


def test_blackbox_export_missing_file(broker: BrokerCore, tmp_path: Path) -> None:
    out = tmp_path / "nonexistent.bin"
    result = broker.blackbox_export(out=out)
    assert result.bytes_written == 0


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

def test_recent_lines_after_halt(broker: BrokerCore) -> None:
    broker.halt()
    lines = broker.recent_lines()
    assert len(lines) > 0
    assert any(line.method == "halt" for line in lines)


def test_recent_lines_after_multiple_ops(broker: BrokerCore) -> None:
    broker.halt()
    broker.resume()
    broker.reset()
    lines = broker.recent_lines()
    methods = [line.method for line in lines]
    assert "halt" in methods
    assert "resume" in methods
    assert "reset" in methods


def test_recent_lines_since_seq(broker: BrokerCore) -> None:
    broker.halt()
    broker.resume()
    all_lines = broker.recent_lines()
    assert len(all_lines) >= 2
    first_seq = all_lines[0].seq
    lines_after = broker.recent_lines(since_seq=first_seq + 1)
    assert all(entry.seq >= first_seq + 1 for entry in lines_after)


def test_recent_lines_limit(broker: BrokerCore) -> None:
    for _ in range(10):
        broker.halt()
    lines = broker.recent_lines(limit=3)
    assert len(lines) <= 3


def test_recent_lines_seq_monotonic(broker: BrokerCore) -> None:
    broker.halt()
    broker.resume()
    broker.reset()
    lines = broker.recent_lines()
    seqs = [entry.seq for entry in lines]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_audit_lane_field_set(broker: BrokerCore) -> None:
    broker.itm_stream_start(ports=[0])
    lines = broker.recent_lines()
    itm_lines = [entry for entry in lines if entry.method == "itm_stream_start"]
    assert len(itm_lines) == 1
    assert itm_lines[0].lane == "itm_swo"
