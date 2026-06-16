# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel


class ProgramResult(BaseModel):
    programmed_bytes: int = 0
    duration_s: float = 0.0
    halted: bool = False
    format: str = "elf"


class ProbeState(BaseModel):
    halted: bool | None = None
    pc: int | None = None
    resumed: bool | None = None
    reset: bool | None = None
    halted_after: bool | None = None
    reset_command_echo: str | None = None
    reset_cause_hint: str | None = None


class MemReadResult(BaseModel):
    addr: int = 0
    length: int = 0
    format: str = "bytes"
    value: str | list[str] = ""


class BlackboxExportResult(BaseModel):
    out: Path = Path("/dev/null")
    bytes_written: int = 0
    snapshot_at: datetime = datetime.min
    resolved_addr: int | None = None
    resolved_length: int | None = None
    resolved_from_region: str | None = None


class ItmStreamHandle(BaseModel):
    ports: list[int] = []
    trace_clock_hz: int | None = None


class ItmStreamSummary(BaseModel):
    stopped: bool = False
    bytes_captured: int = 0
    packet_count: int = 0
    overflow_count: int = 0
    artifact_path: Path | None = None


class ItmStreamExport(BaseModel):
    raw_artifact_path: Path = Path("/dev/null")
    decoded_artifact_path: Path | None = None
    bytes_written: int = 0
    packet_count: int = 0
    cpu_clock_hz: int | None = None
    trace_clock_hz: int | None = None


class LaneStatus(BaseModel):
    lane: str = ""
    released: bool | None = None
    resumed: bool | None = None


class LogLine(BaseModel):
    seq: int = 0
    at: datetime = datetime.min
    method: str = ""
    lane: str | None = None
    ok: bool = False
    payload: dict[str, Any] = {}
    session_id: str | None = None


class SessionStatus(BaseModel):
    protocol_version: str = ""
    image_tag: str | None = None
    image_digest: str | None = None
    state: Literal["stopped", "healthy", "unhealthy", "stale", "unknown"] = "unknown"
    target: str | None = None
    probe_uid: str | None = None
    session_id: str | None = None


class ProbeInfo(BaseModel):
    uid: str = ""
    description: str = ""
    vendor_name: str = ""
    product_name: str = ""
    board_name: str | None = None
    board_vendor: str | None = None


class ProbeDiscoverResult(BaseModel):
    probes: list[ProbeInfo] = []


class TargetInfo(BaseModel):
    name: str = ""
    vendor: str = ""
    part_number: str = ""
    part_families: list[str] = []
    source: str = ""
    pdsc_path: Path | None = None


class TargetSuggestResult(BaseModel):
    targets: list[TargetInfo] = []
    query: str = ""
    pack: str | None = None


class PackSearchResult(BaseModel):
    query: str = ""
    output: str = ""


class PackInstallResult(BaseModel):
    pack: str = ""
    installed: bool = False
    output: str = ""


class PackUpdateResult(BaseModel):
    ok: bool = False
    output: str = ""


class PackCacheResetResult(BaseModel):
    removed: list[Path] = []
    rebuilt: bool = False
    duration_ms: int = 0
    output: str = ""
