# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.lanes import ItmSwoLane, LaneSupervisor


def test_itm_swo_lane_start_returns_handle() -> None:
    lane = ItmSwoLane()
    handle = lane.start(ports=[0, 1], cpu_clock_hz=168_000_000)
    assert handle.ports == [0, 1]
    assert handle.trace_clock_hz is None


def test_itm_swo_lane_start_with_trace_clock() -> None:
    lane = ItmSwoLane()
    handle = lane.start(ports=[0], cpu_clock_hz=168_000_000, trace_clock_hz=4_000_000)
    assert handle.trace_clock_hz == 4_000_000


def test_itm_swo_lane_stop_returns_summary() -> None:
    lane = ItmSwoLane()
    lane.start(ports=[0])
    summary = lane.stop()
    assert summary.stopped is True


def test_itm_swo_lane_stop_without_start() -> None:
    lane = ItmSwoLane()
    summary = lane.stop()
    assert summary.stopped is True


def test_lane_status_both_lanes() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    status = supervisor.lane_status()
    assert "swd" in status
    assert "itm_swo" in status


def test_lane_status_initial_state_not_released() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    status = supervisor.lane_status()
    assert status["swd"].released is False
    assert status["itm_swo"].released is False


def test_lane_release_swd() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    result = supervisor.lane_release("swd")
    assert result.lane == "swd"
    assert result.released is True
    assert result.resumed is False


def test_lane_release_itm_swo() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    result = supervisor.lane_release("itm_swo")
    assert result.lane == "itm_swo"
    assert result.released is True


def test_lane_resume_swd() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    supervisor.lane_release("swd")
    result = supervisor.lane_resume("swd")
    assert result.lane == "swd"
    assert result.resumed is True
    assert result.released is False


def test_lane_status_reflects_release() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    supervisor.lane_release("swd")
    status = supervisor.lane_status()
    assert status["swd"].released is True
    assert status["itm_swo"].released is False


def test_lane_status_reflects_resume_after_release() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    supervisor.lane_release("swd")
    supervisor.lane_resume("swd")
    status = supervisor.lane_status()
    assert status["swd"].released is False


def test_lane_release_unknown_raises() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    with pytest.raises(ValueError, match="unknown lane"):
        supervisor.lane_release("nonexistent")


def test_lane_resume_unknown_raises() -> None:
    config = BrokerConfig()
    supervisor = LaneSupervisor(config=config)
    with pytest.raises(ValueError, match="unknown lane"):
        supervisor.lane_resume("nonexistent")


def test_lane_supervisor_custom_lanes() -> None:
    config = BrokerConfig(lanes=["swd"])
    supervisor = LaneSupervisor(config=config)
    status = supervisor.lane_status()
    assert "swd" in status
    assert "itm_swo" not in status
