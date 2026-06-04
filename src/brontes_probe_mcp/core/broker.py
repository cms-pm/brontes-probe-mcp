# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from typing import Literal

from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import (
    BlackboxExportResult,
    ItmStreamHandle,
    ItmStreamSummary,
    LaneStatus,
    LogLine,
    MemReadResult,
    ProbeState,
    ProgramResult,
    SessionStatus,
)


class BrokerCore:
    def __init__(self, config: BrokerConfig | None = None) -> None:
        self._config: BrokerConfig = config if config is not None else BrokerConfig()

    def program(
        self,
        artifact: Path,
        format: Literal["elf", "bin", "hex"] = "elf",
        address: int | None = None,
        halt_after: bool = True,
        reset_after: bool = False,
    ) -> ProgramResult:
        raise NotImplementedError("8.7.2b implementation")

    def halt(self) -> ProbeState:
        raise NotImplementedError("8.7.2b implementation")

    def resume(self, disconnect_gdb: bool = True) -> ProbeState:
        raise NotImplementedError("8.7.2b implementation")

    def reset(
        self,
        kind: Literal["soft", "hard"] = "soft",
        halt_after: bool = False,
    ) -> ProbeState:
        raise NotImplementedError("8.7.2b implementation")

    def mem_read(
        self,
        addr: int,
        length: int,
        format: Literal["hex", "bytes"] = "hex",
    ) -> MemReadResult:
        raise NotImplementedError("8.7.2b implementation")

    def blackbox_export(self, out: Path) -> BlackboxExportResult:
        raise NotImplementedError("8.7.2b implementation")

    def itm_stream_start(
        self,
        ports: list[int],
        cpu_clock_hz: int | None = None,
        trace_clock_hz: int | None = None,
    ) -> ItmStreamHandle:
        raise NotImplementedError("8.7.2b implementation")

    def itm_stream_stop(self) -> ItmStreamSummary:
        raise NotImplementedError("8.7.2b implementation")

    def lane_status(self) -> dict[str, LaneStatus]:
        raise NotImplementedError("8.7.2b implementation")

    def lane_release(self, lane: str) -> LaneStatus:
        raise NotImplementedError("8.7.2b implementation")

    def lane_resume(self, lane: str) -> LaneStatus:
        raise NotImplementedError("8.7.2b implementation")

    def recent_lines(
        self,
        since_seq: int = 0,
        limit: int = 100,
    ) -> list[LogLine]:
        raise NotImplementedError("8.7.2b implementation")

    def session_start(self, **profile_kwargs: object) -> SessionStatus:
        raise NotImplementedError("8.7.2b implementation")

    def session_stop(self, force: bool = False) -> SessionStatus:
        raise NotImplementedError("8.7.2b implementation")

    def session_status(self) -> SessionStatus:
        raise NotImplementedError("8.7.2b implementation")
