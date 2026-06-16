# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.1 H4 — blackbox_export ergonomics.

Acceptance: SCN-2.1.1-BLACKBOX-NO-DEFAULTS, SCN-2.1.1-BLACKBOX-ADDR-LENGTH,
SCN-2.1.1-BLACKBOX-REGION.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import BlackboxExportResult


def _completed(stdout: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _hex_words(n: int) -> str:
    return "0x20000000:\t" + "\t".join(["0xdeadbeef"] * n) + "\n"


@pytest.fixture()
def broker_with_session(tmp_path: Path) -> BrokerCore:
    mock_run = MagicMock(return_value=_completed(_hex_words(16)))
    mock_popen = MagicMock(spec=subprocess.Popen)
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    broker = BrokerCore(
        config=config,
        _subprocess_run=mock_run,
        _subprocess_popen=MagicMock(return_value=mock_popen),
    )
    broker._session_state = "healthy"
    return broker


def test_no_range_raises_value_error(
    broker_with_session: BrokerCore, tmp_path: Path
) -> None:
    out = tmp_path / "snap.bin"
    with pytest.raises(ValueError) as excinfo:
        broker_with_session.blackbox_export(out=out)
    msg = str(excinfo.value)
    assert "start_addr" in msg
    assert "addr" in msg
    assert "region" in msg


def test_addr_length_form_writes_exactly_length_bytes(
    broker_with_session: BrokerCore, tmp_path: Path
) -> None:
    out = tmp_path / "addr-length.bin"
    result = broker_with_session.blackbox_export(
        out=out, addr=0x20000000, length=64
    )
    assert isinstance(result, BlackboxExportResult)
    assert result.bytes_written == 64
    assert out.stat().st_size == 64
    assert result.resolved_addr == 0x20000000
    assert result.resolved_length == 64
    assert result.resolved_from_region is None


def test_start_end_form_still_works(
    broker_with_session: BrokerCore, tmp_path: Path
) -> None:
    out = tmp_path / "start-end.bin"
    result = broker_with_session.blackbox_export(
        out=out, start_addr=0x20000000, end_addr=0x20000040
    )
    assert result.bytes_written == 64
    assert result.resolved_addr == 0x20000000
    assert result.resolved_length == 64


def test_named_region_resolves_to_addr_length(
    broker_with_session: BrokerCore, tmp_path: Path
) -> None:
    out = tmp_path / "region.bin"
    result = broker_with_session.blackbox_export(out=out, region="sram_blackbox")
    assert result.bytes_written == 64
    assert result.resolved_addr == 0x20000000
    assert result.resolved_length == 64
    assert result.resolved_from_region == "sram_blackbox"


def test_unknown_region_raises_value_error(
    broker_with_session: BrokerCore, tmp_path: Path
) -> None:
    out = tmp_path / "unknown.bin"
    with pytest.raises(ValueError, match="unknown region"):
        broker_with_session.blackbox_export(
            out=out, region="this_region_does_not_exist"
        )


def test_zero_length_raises_value_error(
    broker_with_session: BrokerCore, tmp_path: Path
) -> None:
    out = tmp_path / "zero.bin"
    with pytest.raises(ValueError, match="positive"):
        broker_with_session.blackbox_export(out=out, addr=0x20000000, length=0)
