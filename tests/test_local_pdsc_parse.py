# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.2 H2 — local PDSC bypass for target_suggest.

Acceptance: SCN-2.1.2-LOCAL-PDSC.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.errors import PackParseError

_FIXTURES = Path(__file__).parent / "fixtures"


def _completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> CompletedProcess[str]:
    return CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture()
def broker_with_failing_subprocess(tmp_path: Path) -> tuple[BrokerCore, MagicMock]:
    """Subprocess fails if invoked — proves local-PDSC bypass skips pyOCD."""
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    mock_run = MagicMock(
        return_value=_completed(returncode=1, stderr="should not be called")
    )
    broker = BrokerCore(
        config=config,
        _subprocess_run=mock_run,
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )
    return broker, mock_run


def test_target_suggest_with_local_pdsc_skips_pyocd(
    broker_with_failing_subprocess: tuple[BrokerCore, MagicMock],
) -> None:
    broker, mock_run = broker_with_failing_subprocess
    pdsc_dir = _FIXTURES / "pdsc"
    result = broker.target_suggest(query="STM32G474", pack=str(pdsc_dir))
    # No pyocd subprocess invocation when local PDSC succeeds.
    mock_run.assert_not_called()
    assert len(result.targets) >= 1
    names = {t.name for t in result.targets}
    assert "stm32g474ceux" in names
    first = next(t for t in result.targets if t.name == "stm32g474ceux")
    assert first.source == "local_pdsc"
    assert first.pdsc_path == pdsc_dir / "STM32G4xx_DFP.pdsc"
    assert first.vendor == "STMicroelectronics"


def test_target_suggest_partial_query_matches_family(
    broker_with_failing_subprocess: tuple[BrokerCore, MagicMock],
) -> None:
    broker, _ = broker_with_failing_subprocess
    result = broker.target_suggest(query="stm32g4", pack=str(_FIXTURES / "pdsc"))
    # All devices in the family should match.
    assert len(result.targets) == 2


def test_target_suggest_malformed_pdsc_raises_typed_error(
    broker_with_failing_subprocess: tuple[BrokerCore, MagicMock],
) -> None:
    broker, _ = broker_with_failing_subprocess
    malformed_dir = _FIXTURES / "pdsc_malformed"
    with pytest.raises(PackParseError) as excinfo:
        broker.target_suggest(query="stm32", pack=str(malformed_dir))
    assert "Broken.pdsc" in excinfo.value.pdsc_path


def test_target_suggest_empty_pack_dir_falls_through_to_pyocd(
    tmp_path: Path,
) -> None:
    """No .pdsc in the dir → fall through to global pyocd path."""
    empty_dir = tmp_path / "empty-pack"
    empty_dir.mkdir()
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    mock_run = MagicMock(
        return_value=_completed(stdout='{"targets": []}')
    )
    broker = BrokerCore(
        config=config,
        _subprocess_run=mock_run,
        _subprocess_popen=MagicMock(spec=subprocess.Popen),
    )
    broker.target_suggest(query="stm32g4", pack=str(empty_dir))
    mock_run.assert_called_once()
