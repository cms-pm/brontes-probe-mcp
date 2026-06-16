# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.2 H2 — corrupt pack-index detection.

Acceptance: SCN-2.1.2-PACK-TYPED-ERROR.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.errors import PackIndexCorruptError

# The literal corruption signature from the retrospective.
_STDERR_CORRUPT = (
    "Traceback (most recent call last):\n"
    "  File \"<...>\", line 1, in <module>\n"
    "    json.loads(idx)\n"
    "json.decoder.JSONDecodeError: Extra data: line 1272628 column 7 "
    "(char 50331648)\n"
)


def _completed(
    stdout: str = "", returncode: int = 1, stderr: str = ""
) -> CompletedProcess[str]:
    return CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture()
def broker(tmp_path: Path) -> BrokerCore:
    config = BrokerConfig(
        log_dir=str(tmp_path / "logs"),
        pyocd_pack_index_dir=str(tmp_path / "fake-pack-index"),
    )
    return BrokerCore(
        config=config,
        _subprocess_run=MagicMock(return_value=_completed(stderr=_STDERR_CORRUPT)),
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )


def test_pack_search_raises_typed_error_on_corrupt_index(broker: BrokerCore) -> None:
    with pytest.raises(PackIndexCorruptError) as excinfo:
        broker.pack_search("STM32G4")
    err = excinfo.value
    assert err.remediation == "brontes-probe-mcp-cli call pack_cache_reset"
    assert "Extra data: line 1272628 column 7" in err.cause_message
    assert "fake-pack-index" in err.index_path_hint


def test_pack_install_raises_typed_error_on_corrupt_index(broker: BrokerCore) -> None:
    with pytest.raises(PackIndexCorruptError):
        broker.pack_install("Keil.STM32G4xx_DFP")


def test_pack_update_raises_typed_error_on_corrupt_index(broker: BrokerCore) -> None:
    with pytest.raises(PackIndexCorruptError):
        broker.pack_update()


def test_target_suggest_raises_typed_error_on_corrupt_index(broker: BrokerCore) -> None:
    with pytest.raises(PackIndexCorruptError):
        broker.target_suggest("STM32G474")


def test_corrupt_signature_in_stdout_also_caught(tmp_path: Path) -> None:
    """pyOCD sometimes streams the traceback to stdout instead of stderr."""
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    broker = BrokerCore(
        config=config,
        _subprocess_run=MagicMock(
            return_value=_completed(stdout=_STDERR_CORRUPT, stderr="")
        ),
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )
    with pytest.raises(PackIndexCorruptError):
        broker.pack_search("STM32G4")
