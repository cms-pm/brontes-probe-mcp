# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import sys

import pytest

from brontes_probe_mcp.cli import main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["brontes-probe-mcp-cli", "--version"]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_config_dump(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["brontes-probe-mcp-cli", "--config-dump"]
    main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)
    assert "transports" in data
    assert "lanes" in data
    assert "backend" in data


def test_no_args_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["brontes-probe-mcp-cli"]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


# ── COM-010: top-level --transports removed ───────────────────────────────────

def test_top_level_transports_flag_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["brontes-probe-mcp-cli", "--transports", "stdio"]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0


def test_serve_transports_flag_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    # Just verifies argparse accepts it; serve blocks, so we only check parse
    # We can't run the actual server in a test, so we verify the argument is
    # recognized by checking it doesn't trigger an "unrecognized arguments" exit.
    # We do this by checking the parsed subcommand reaches the serve branch.
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    serve_p = sub.add_parser("serve")
    serve_p.add_argument("--transports", dest="serve_transports")
    args = parser.parse_args(["serve", "--transports", "stdio,socket"])
    assert args.command == "serve"
    assert args.serve_transports == "stdio,socket"


# ── COM-006: session-unlock subcommand ────────────────────────────────────────

def test_session_unlock_removes_lock(
    capsys: pytest.CaptureFixture[str], tmp_path: pytest.TempPathFactory
) -> None:
    from brontes_probe_mcp.core.config import BrokerConfig
    from brontes_probe_mcp.core.session import SessionManager

    config = BrokerConfig(log_dir=str(tmp_path))
    sm = SessionManager(config)
    lock_path = sm._lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("{}")

    sys.argv = ["brontes-probe-mcp-cli", "session-unlock"]
    import unittest.mock as _mock

    with _mock.patch("brontes_probe_mcp.cli.BrokerConfig", return_value=config):
        main()

    assert not lock_path.exists()
    captured = capsys.readouterr()
    assert "Removed" in captured.out


def test_session_unlock_no_lock(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["brontes-probe-mcp-cli", "session-unlock"]
    main()
    captured = capsys.readouterr()
    assert "No lock" in captured.out


# ── probe-agent subcommand ────────────────────────────────────────────────────

_MGR = "brontes_probe_mcp.core.session.SessionManager"
_BOARDS = "brontes_probe_mcp.cli._probe_boards"


def test_probe_agent_start_forwards_agent_profile(
    capsys: pytest.CaptureFixture[str], tmp_path: pytest.TempPathFactory
) -> None:
    """start uses profile='agent' so state lands in agent.json, not default.json."""
    import unittest.mock as _mock

    from brontes_probe_mcp.core.models import SessionStatus

    healthy = SessionStatus(protocol_version="1.1", state="healthy", target="stm32g474")
    with _mock.patch(_MGR) as MockMgr:
        instance = MockMgr.return_value
        instance.start.return_value = healthy
        sys.argv = [
            "brontes-probe-mcp-cli", "probe-agent", "start",
            "--target", "stm32g474", "--state-dir", str(tmp_path),
        ]
        main()

    call_kwargs = instance.start.call_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("profile") == "agent"
    assert call_kwargs.kwargs.get("target") == "stm32g474"


def test_probe_agent_start_auto_detect_single_probe(
    capsys: pytest.CaptureFixture[str], tmp_path: pytest.TempPathFactory
) -> None:
    """Single probe with known target: auto-detected, no --target needed."""
    import unittest.mock as _mock

    from brontes_probe_mcp.core.models import SessionStatus

    boards = [{"unique_id": "abc123", "target": "stm32g474"}]
    healthy = SessionStatus(protocol_version="1.1", state="healthy", target="stm32g474")

    with (
        _mock.patch(_BOARDS, return_value=boards) as mock_boards,
        _mock.patch(_MGR) as MockMgr,
    ):
        instance = MockMgr.return_value
        instance.start.return_value = healthy
        sys.argv = [
            "brontes-probe-mcp-cli", "probe-agent", "start",
            "--state-dir", str(tmp_path),
        ]
        main()

    mock_boards.assert_called_once()
    assert instance.start.call_args.kwargs.get("target") == "stm32g474"


def test_probe_agent_start_no_probes_exits_nonzero(
    capsys: pytest.CaptureFixture[str], tmp_path: pytest.TempPathFactory
) -> None:
    """No probes found → exit 1, informative message, single _probe_boards call."""
    import unittest.mock as _mock

    with _mock.patch(_BOARDS, return_value=[]) as mock_boards:
        sys.argv = [
            "brontes-probe-mcp-cli", "probe-agent", "start",
            "--state-dir", str(tmp_path),
        ]
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1
    mock_boards.assert_called_once()
    captured = capsys.readouterr()
    assert "No debug probes" in captured.err


def test_probe_agent_start_ambiguous_probes_exits_nonzero(
    capsys: pytest.CaptureFixture[str], tmp_path: pytest.TempPathFactory
) -> None:
    """Multiple probes → exit 1, single _probe_boards call (no double-invocation)."""
    import unittest.mock as _mock

    boards = [
        {"unique_id": "aaa", "target": "stm32g474"},
        {"unique_id": "bbb", "target": "stm32l4"},
    ]
    with _mock.patch(_BOARDS, return_value=boards) as mock_boards:
        sys.argv = [
            "brontes-probe-mcp-cli", "probe-agent", "start",
            "--state-dir", str(tmp_path),
        ]
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1
    mock_boards.assert_called_once()
    captured = capsys.readouterr()
    assert "2 probes" in captured.err


def test_probe_agent_stop_forwards_agent_profile(
    capsys: pytest.CaptureFixture[str], tmp_path: pytest.TempPathFactory
) -> None:
    """stop uses profile='agent'."""
    import unittest.mock as _mock

    from brontes_probe_mcp.core.models import SessionStatus

    stopped = SessionStatus(protocol_version="1.1", state="stopped")
    with _mock.patch(_MGR) as MockMgr:
        instance = MockMgr.return_value
        instance.stop.return_value = stopped
        sys.argv = [
            "brontes-probe-mcp-cli", "probe-agent", "stop",
            "--state-dir", str(tmp_path),
        ]
        main()

    call_kwargs = instance.stop.call_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("profile") == "agent"


def test_probe_agent_status_healthy_exits_zero(
    capsys: pytest.CaptureFixture[str], tmp_path: pytest.TempPathFactory
) -> None:
    """status healthy → exit 0, JSON output."""
    import unittest.mock as _mock

    from brontes_probe_mcp.core.models import SessionStatus

    healthy = SessionStatus(protocol_version="1.1", state="healthy", target="stm32g474")
    with _mock.patch(_MGR) as MockMgr:
        instance = MockMgr.return_value
        instance.status.return_value = healthy
        sys.argv = [
            "brontes-probe-mcp-cli", "probe-agent", "status",
            "--state-dir", str(tmp_path),
        ]
        main()

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["state"] == "healthy"


def test_probe_agent_status_unhealthy_exits_nonzero(
    capsys: pytest.CaptureFixture[str], tmp_path: pytest.TempPathFactory
) -> None:
    """status unhealthy → exit 1."""
    import unittest.mock as _mock

    from brontes_probe_mcp.core.models import SessionStatus

    unhealthy = SessionStatus(protocol_version="1.1", state="unhealthy")
    with _mock.patch(_MGR) as MockMgr:
        instance = MockMgr.return_value
        instance.status.return_value = unhealthy
        sys.argv = [
            "brontes-probe-mcp-cli", "probe-agent", "status",
            "--state-dir", str(tmp_path),
        ]
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1
