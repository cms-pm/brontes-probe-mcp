# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import ItmStreamHandle, ItmStreamSummary, LaneStatus


class ItmSwoLane:
    """ITM/SWO lane — records streaming intent.

    Actual byte-stream capture is a post-1.x enhancement.
    """

    def __init__(self) -> None:
        self._active = False
        self._ports: list[int] = []
        self._cpu_clock_hz: int | None = None
        self._trace_clock_hz: int | None = None

    def start(
        self,
        ports: list[int],
        cpu_clock_hz: int | None = None,
        trace_clock_hz: int | None = None,
    ) -> ItmStreamHandle:
        self._active = True
        self._ports = list(ports)
        self._cpu_clock_hz = cpu_clock_hz
        self._trace_clock_hz = trace_clock_hz
        return ItmStreamHandle(ports=self._ports, trace_clock_hz=trace_clock_hz)

    def stop(self) -> ItmStreamSummary:
        self._active = False
        self._ports = []
        return ItmStreamSummary(stopped=True)


class LaneSupervisor:
    def __init__(self, config: BrokerConfig) -> None:
        self._config = config
        self.itm_swo = ItmSwoLane()
        # True = normal/active; False = released
        self._lane_states: dict[str, bool] = dict.fromkeys(config.lanes, True)

    def _require_lane(self, lane: str) -> None:
        if lane not in self._lane_states:
            raise ValueError(
                f"unknown lane {lane!r}; configured lanes: {list(self._lane_states)}"
            )

    def lane_status(self) -> dict[str, LaneStatus]:
        result: dict[str, LaneStatus] = {}
        for lane, active in self._lane_states.items():
            result[lane] = LaneStatus(
                lane=lane,
                released=not active,
                resumed=active,
            )
        return result

    def lane_release(self, lane: str) -> LaneStatus:
        self._require_lane(lane)
        self._lane_states[lane] = False
        return LaneStatus(lane=lane, released=True, resumed=False)

    def lane_resume(self, lane: str) -> LaneStatus:
        self._require_lane(lane)
        self._lane_states[lane] = True
        return LaneStatus(lane=lane, released=False, resumed=True)
