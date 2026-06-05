# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports.stdio import _call_handler


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


def _call(broker: BrokerCore, name: str, arguments: dict[str, Any]) -> Any:
    result_json = asyncio.run(_call_handler(broker, name, arguments))
    return json.loads(result_json)


def test_halt_tool(broker_instance: BrokerCore) -> None:
    result = _call(broker_instance, "probe_halt", {})
    assert result.get("halted") is True


def test_probe_flash_alias(broker_instance: BrokerCore, tmp_path: Path) -> None:
    elf = tmp_path / "fw.elf"
    elf.write_bytes(b"\x00" * 64)
    result = _call(broker_instance, "probe_flash", {"artifact": str(elf)})
    assert "programmed_bytes" in result


def test_probe_program(broker_instance: BrokerCore, tmp_path: Path) -> None:
    elf = tmp_path / "fw.elf"
    elf.write_bytes(b"\x00" * 64)
    result = _call(broker_instance, "probe_program", {"artifact": str(elf)})
    assert "programmed_bytes" in result


def test_unknown_tool_returns_error(broker_instance: BrokerCore) -> None:
    result = _call(broker_instance, "no_such_tool", {})
    assert "error" in result


def test_session_status(broker_instance: BrokerCore) -> None:
    result = _call(broker_instance, "session_status", {})
    assert "state" in result


def test_recent_lines_wrapper(broker_instance: BrokerCore) -> None:
    result = _call(broker_instance, "recent_lines", {})
    assert "next_seq" in result
    assert "lines" in result


def test_lane_status(broker_instance: BrokerCore) -> None:
    result = _call(broker_instance, "lane_status", {})
    assert isinstance(result, dict)
    assert "swd" in result or "itm_swo" in result


def test_probe_op_without_session_returns_session_required(
    mock_run: MagicMock, mock_popen: MagicMock, tmp_path: Path
) -> None:
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    no_session_broker = BrokerCore(
        config=config, _subprocess_run=mock_run, _subprocess_popen=mock_popen
    )
    result = _call(no_session_broker, "probe_halt", {})
    assert "error" in result
    assert result["error"]["kind"] == "session_required"


def test_all_15_tools_callable(broker_instance: BrokerCore, tmp_path: Path) -> None:
    elf = tmp_path / "fw.elf"
    elf.write_bytes(b"\x00" * 64)
    out = tmp_path / "export.bin"
    out.write_bytes(b"\xde\xad" * 4)

    # Non-GDB tools: callable regardless of session state
    non_gdb_tools: list[tuple[str, dict[str, Any]]] = [
        ("session_status", {}),
        ("itm_stream_start", {"ports": [0]}),
        ("itm_stream_stop", {}),
        ("lane_status", {}),
        ("lane_release", {"lane": "swd"}),
        ("lane_resume", {"lane": "swd"}),
        ("recent_lines", {}),
        ("probe_blackbox_export", {"out": str(out)}),
    ]
    for name, args in non_gdb_tools:
        result = _call(broker_instance, name, args)
        assert "error" not in result, f"Tool {name!r} returned error: {result}"

    # GDB-backed tools: require healthy session — broker_instance has one
    gdb_tools: list[tuple[str, dict[str, Any]]] = [
        ("probe_halt", {}),
        ("probe_resume", {}),
        ("probe_reset", {}),
        ("probe_mem_read", {"addr": 0x20000000, "length": 4}),
        ("probe_program", {"artifact": str(elf)}),
        ("probe_flash", {"artifact": str(elf)}),
    ]
    for name, args in gdb_tools:
        result = _call(broker_instance, name, args)
        assert "error" not in result, f"Tool {name!r} returned error: {result}"
