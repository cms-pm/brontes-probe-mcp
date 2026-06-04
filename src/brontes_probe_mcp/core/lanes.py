# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import ItmStreamHandle, ItmStreamSummary, LaneStatus


class ItmSwoLane:
    def start(
        self,
        ports: list[int],
        cpu_clock_hz: int | None = None,
        trace_clock_hz: int | None = None,
    ) -> ItmStreamHandle:
        raise NotImplementedError("8.7.2a implementation")

    def stop(self) -> ItmStreamSummary:
        raise NotImplementedError("8.7.2a implementation")


class LaneSupervisor:
    def __init__(self, config: BrokerConfig) -> None:
        self._config = config
        self.itm_swo = ItmSwoLane()

    def lane_status(self) -> dict[str, LaneStatus]:
        raise NotImplementedError("8.7.2a implementation")

    def lane_release(self, lane: str) -> LaneStatus:
        raise NotImplementedError("8.7.2a implementation")

    def lane_resume(self, lane: str) -> LaneStatus:
        raise NotImplementedError("8.7.2a implementation")
