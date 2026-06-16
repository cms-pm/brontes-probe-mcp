# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.2 H3 — reset-kind catalog and command echo.

Acceptance: SCN-2.1.2-RESET-CATALOG, SCN-2.1.2-RESET-ECHO,
SCN-2.1.2-RESET-DOC-WATCHDOG.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import ProbeState

_KINDS_TO_COMMAND: dict[str, str] = {
    "soft": "monitor reset soft",
    "hard": "monitor reset hard",
    "sw": "monitor reset sw",
    "system": "monitor reset system",
    "core": "monitor reset core",
    "backend_default": "monitor reset",
}


def _completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> CompletedProcess[str]:
    return CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture()
def broker_with_session(tmp_path: Path) -> tuple[BrokerCore, MagicMock]:
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    mock_run = MagicMock(return_value=_completed(stdout="reset done\n"))
    broker = BrokerCore(
        config=config,
        _subprocess_run=mock_run,
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )
    broker._session_state = "healthy"
    return broker, mock_run


@pytest.mark.parametrize("kind,expected_cmd", list(_KINDS_TO_COMMAND.items()))
def test_each_reset_kind_maps_to_expected_command(
    broker_with_session: tuple[BrokerCore, MagicMock],
    kind: str,
    expected_cmd: str,
) -> None:
    broker, mock_run = broker_with_session
    # Type ignore: parametrized strings include non-Literal values from the
    # catalog; runtime validation lives in BrokerCore.reset.
    state: ProbeState = broker.reset(kind=kind)  # type: ignore[arg-type]
    assert state.reset is True
    assert state.reset_command_echo == expected_cmd

    cmd_args: list[Any] = mock_run.call_args[0][0]
    assert any(expected_cmd == str(a) for a in cmd_args), (
        f"Expected {expected_cmd!r} in GDB args, got {cmd_args}"
    )


def test_reset_unknown_kind_raises_value_error(
    broker_with_session: tuple[BrokerCore, MagicMock],
) -> None:
    broker, _ = broker_with_session
    with pytest.raises(ValueError, match="unknown reset kind"):
        broker.reset(kind="bogus")  # type: ignore[arg-type]


def test_reset_cause_hint_populated_from_gdb_output(
    broker_with_session: tuple[BrokerCore, MagicMock],
) -> None:
    broker, mock_run = broker_with_session
    mock_run.return_value = _completed(
        stdout="SYSRESETREQ asserted\nremote target reset complete\n"
    )
    state = broker.reset(kind="sw")
    assert state.reset_cause_hint == "SYSRESETREQ asserted"


def test_reset_halt_after_appends_monitor_halt(
    broker_with_session: tuple[BrokerCore, MagicMock],
) -> None:
    broker, mock_run = broker_with_session
    state = broker.reset(kind="soft", halt_after=True)
    assert state.halted_after is True
    cmd_args = mock_run.call_args[0][0]
    assert any("monitor halt" == str(a) for a in cmd_args)


def test_reset_docstring_mentions_watchdog_masking() -> None:
    """SCN-2.1.2-RESET-DOC-WATCHDOG — IWDG masking warning is in the docstring."""
    doc = BrokerCore.reset.__doc__ or ""
    assert "watchdog" in doc.lower() or "iwdg" in doc.lower()
    assert "mask" in doc.lower()


def test_reset_catalog_documented_in_docstring() -> None:
    """Each reset kind appears in the docstring."""
    doc = BrokerCore.reset.__doc__ or ""
    for kind in _KINDS_TO_COMMAND:
        assert kind in doc, f"Reset kind {kind!r} not mentioned in docstring"
