# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.3 H5 — audit log session correlation.

Acceptance: SCN-2.1.3-LOGLINE-SESSION-ID, SCN-2.1.3-AUDIT-SCOPED,
SCN-2.1.3-AUDIT-BACKCOMPAT.
"""
from __future__ import annotations

import json
from pathlib import Path

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import LogLine
from brontes_probe_mcp.core.session import SessionManager


def _make_broker(tmp_path: Path) -> BrokerCore:
    return BrokerCore(config=BrokerConfig(log_dir=str(tmp_path / "logs")))


def test_logline_session_id_field_is_optional_none() -> None:
    line = LogLine(seq=1, method="halt")
    assert line.session_id is None


def test_audit_entries_stamped_with_active_session_id(tmp_path: Path) -> None:
    broker = _make_broker(tmp_path)
    broker._session_id = "sess-A"
    broker._log_op("halt", payload={})
    broker._log_op("resume", payload={})
    lines = broker.recent_lines()
    assert all(e.session_id == "sess-A" for e in lines)


def test_recent_lines_filters_to_one_session_across_two_sessions(
    tmp_path: Path,
) -> None:
    broker = _make_broker(tmp_path)
    broker._session_id = "sess-A"
    broker._log_op("halt")
    broker._log_op("resume")
    broker._session_id = "sess-B"
    broker._log_op("halt")
    broker._log_op("reset")

    a_only = broker.recent_lines(session_id="sess-A")
    assert {e.method for e in a_only} == {"halt", "resume"}
    assert all(e.session_id == "sess-A" for e in a_only)

    b_only = broker.recent_lines(session_id="sess-B")
    assert {e.method for e in b_only} == {"halt", "reset"}
    assert all(e.session_id == "sess-B" for e in b_only)


def test_recent_lines_default_returns_all_back_compat(tmp_path: Path) -> None:
    broker = _make_broker(tmp_path)
    broker._session_id = "sess-A"
    broker._log_op("halt")
    broker._session_id = None
    broker._log_op("probe_discover")
    all_lines = broker.recent_lines()
    assert len(all_lines) == 2
    # back-compat: passing only since_seq still works.
    assert len(broker.recent_lines(since_seq=2)) == 1


def test_session_id_cleared_after_session_stop(tmp_path: Path) -> None:
    broker = _make_broker(tmp_path)
    broker._session_id = "sess-A"
    broker._log_op("halt")
    broker.session_stop()
    broker._log_op("probe_discover")
    discoverable = broker.recent_lines(method="probe_discover")
    assert len(discoverable) == 1
    assert discoverable[0].session_id is None


def test_session_status_round_trips_session_id_from_meta(tmp_path: Path) -> None:
    """SessionManager.status() reads session_id back from on-disk meta.

    Direct unit on the persistence path — complements the broker-level
    tests above, which set ``_session_id`` directly without touching
    the meta file.
    """
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    mgr = SessionManager(config=config)
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "backend": "pyocd",
        "gdb_host": "127.0.0.1",
        "gdb_port": config.gdb_port,
        "target": "stm32g4",
        "session_id": "round-trip-sentinel",
    }
    (log_dir / "default.json").write_text(json.dumps(meta))
    # Meta has no pid → _derive_state goes straight to the TCP probe,
    # which will fail closed (unhealthy) on a free local port — fine.
    status = mgr.status()
    assert status.session_id == "round-trip-sentinel"
    assert status.target == "stm32g4"
