# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.3 H5 — recent_lines method/lane filters.

Acceptance: SCN-2.1.3-AUDIT-METHOD-FILTER, SCN-2.1.3-AUDIT-LANE-FILTER.
"""
from __future__ import annotations

from pathlib import Path

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig


def _seeded(tmp_path: Path) -> BrokerCore:
    broker = BrokerCore(config=BrokerConfig(log_dir=str(tmp_path / "logs")))
    broker._session_id = "sess-A"
    broker._log_op("halt")
    broker._log_op("resume")
    broker._log_op("itm_stream_start", lane="itm_swo")
    broker._session_id = "sess-B"
    broker._log_op("halt")
    broker._log_op("itm_stream_stop", lane="itm_swo")
    return broker


def test_method_filter_returns_only_matching_method(tmp_path: Path) -> None:
    broker = _seeded(tmp_path)
    halts = broker.recent_lines(method="halt")
    assert len(halts) == 2
    assert {e.session_id for e in halts} == {"sess-A", "sess-B"}
    assert all(e.method == "halt" for e in halts)


def test_lane_filter_returns_only_matching_lane(tmp_path: Path) -> None:
    broker = _seeded(tmp_path)
    itm = broker.recent_lines(lane="itm_swo")
    assert len(itm) == 2
    assert {e.method for e in itm} == {"itm_stream_start", "itm_stream_stop"}


def test_filters_and_together_session_and_lane(tmp_path: Path) -> None:
    broker = _seeded(tmp_path)
    a_itm = broker.recent_lines(session_id="sess-A", lane="itm_swo")
    assert len(a_itm) == 1
    assert a_itm[0].method == "itm_stream_start"


def test_filters_and_together_session_and_method(tmp_path: Path) -> None:
    broker = _seeded(tmp_path)
    a_halt = broker.recent_lines(session_id="sess-A", method="halt")
    assert len(a_halt) == 1
    assert a_halt[0].session_id == "sess-A"


def test_no_match_returns_empty(tmp_path: Path) -> None:
    broker = _seeded(tmp_path)
    assert broker.recent_lines(method="nope") == []
    assert broker.recent_lines(session_id="ghost") == []


def test_limit_applies_after_filters(tmp_path: Path) -> None:
    broker = _seeded(tmp_path)
    one_halt = broker.recent_lines(method="halt", limit=1)
    assert len(one_halt) == 1
