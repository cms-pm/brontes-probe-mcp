# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.2 H2 — pack_cache_reset.

Acceptance: SCN-2.1.2-PACK-CACHE-RESET.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import PackCacheResetResult


def _completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> CompletedProcess[str]:
    return CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture()
def index_dir_with_files(tmp_path: Path) -> Path:
    idx = tmp_path / "pack-index"
    idx.mkdir()
    (idx / "Keil.pidx").write_bytes(b"malformed json {{{")
    (idx / "vendor.pidx").write_bytes(b"more malformed")
    return idx


def test_pack_cache_reset_removes_index_files_and_rebuilds(
    index_dir_with_files: Path, tmp_path: Path
) -> None:
    config = BrokerConfig(
        log_dir=str(tmp_path / "logs"),
        pyocd_pack_index_dir=str(index_dir_with_files),
    )
    mock_run = MagicMock(return_value=_completed(stdout="pack index updated"))
    broker = BrokerCore(
        config=config,
        _subprocess_run=mock_run,
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )

    result = broker.pack_cache_reset()

    assert isinstance(result, PackCacheResetResult)
    assert result.rebuilt is True
    assert len(result.removed) == 2
    assert all(not p.exists() for p in result.removed)
    assert result.duration_ms >= 0
    # Subprocess called pyocd pack update
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "pack" in cmd and "update" in cmd


def test_pack_cache_reset_handles_missing_index_dir(tmp_path: Path) -> None:
    config = BrokerConfig(
        log_dir=str(tmp_path / "logs"),
        pyocd_pack_index_dir=str(tmp_path / "does-not-exist"),
    )
    broker = BrokerCore(
        config=config,
        _subprocess_run=MagicMock(return_value=_completed()),
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )
    result = broker.pack_cache_reset()
    assert result.removed == []
    assert result.rebuilt is True


def test_pack_cache_reset_rebuilt_false_when_update_fails(
    index_dir_with_files: Path, tmp_path: Path
) -> None:
    config = BrokerConfig(
        log_dir=str(tmp_path / "logs"),
        pyocd_pack_index_dir=str(index_dir_with_files),
    )
    broker = BrokerCore(
        config=config,
        _subprocess_run=MagicMock(
            return_value=_completed(returncode=1, stderr="network down")
        ),
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )
    result = broker.pack_cache_reset()
    assert result.rebuilt is False
    assert len(result.removed) == 2  # files still get removed
