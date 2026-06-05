# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.lanes import LaneSupervisor
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
from brontes_probe_mcp.core.session import SessionManager


class SessionRequiredError(RuntimeError):
    """Raised when a probe operation is attempted without a healthy session."""


class BrokerCore:
    def __init__(
        self,
        config: BrokerConfig | None = None,
        _subprocess_run: Callable[..., Any] | None = None,
        _subprocess_popen: Callable[..., subprocess.Popen[bytes]] | None = None,
    ) -> None:
        self._config: BrokerConfig = config if config is not None else BrokerConfig()
        self._subprocess_run: Callable[..., Any] = _subprocess_run or subprocess.run
        self._subprocess_popen: Callable[..., subprocess.Popen[bytes]] = (
            _subprocess_popen or subprocess.Popen
        )
        self._sessions = SessionManager(
            config=self._config, _popen=self._subprocess_popen
        )
        self._lanes = LaneSupervisor(config=self._config)
        self._audit: deque[LogLine] = deque(maxlen=256)
        self._audit_lock = threading.Lock()
        self._seq = 0
        self._session_state: str = "stopped"

    def _log_op(
        self,
        method: str,
        lane: str | None = None,
        ok: bool = True,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._audit_lock:
            self._seq += 1
            entry = LogLine(
                seq=self._seq,
                at=datetime.now(tz=UTC),
                method=method,
                lane=lane,
                ok=ok,
                payload=payload or {},
            )
            self._audit.append(entry)

    def _require_session(self) -> None:
        if self._session_state != "healthy":
            raise SessionRequiredError(
                f"no healthy session active (state={self._session_state!r}); "
                "call session_start first"
            )

    def _run_gdb(self, commands: list[str], symbol_file: Path | None = None) -> str:
        args: list[str] = [
            self._config.gdb_bin,
            "--batch",
            "--nx",
            "-ex",
            f"target remote {self._config.tcp_host}:{self._config.gdb_port}",
        ]
        if symbol_file is not None:
            args.extend(["-ex", f"file {symbol_file}"])
        for cmd in commands:
            args.extend(["-ex", cmd])
        result: Any = self._subprocess_run(
            args, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"GDB exited {result.returncode}: {detail or '(no output)'}"
            )
        return str(result.stdout)

    def program(
        self,
        artifact: Path,
        format: Literal["elf", "bin", "hex"] = "elf",
        address: int | None = None,
        halt_after: bool = True,
        reset_after: bool = False,
    ) -> ProgramResult:
        self._require_session()
        t0 = time.monotonic()
        sym = artifact if format == "elf" else None
        cmds = ["monitor halt", f"load {artifact}"]
        if reset_after:
            cmds.append("monitor reset")
        if halt_after:
            cmds.append("monitor halt")
        self._run_gdb(cmds, symbol_file=sym)
        elapsed = time.monotonic() - t0
        size = artifact.stat().st_size if artifact.exists() else 0
        self._log_op("program", payload={"artifact": str(artifact), "format": format})
        return ProgramResult(
            programmed_bytes=size,
            duration_s=elapsed,
            halted=halt_after,
            format=format,
        )

    def halt(self) -> ProbeState:
        self._require_session()
        self._run_gdb(["monitor halt"])
        self._log_op("halt", payload={"halted": True})
        return ProbeState(halted=True)

    def resume(self, disconnect_gdb: bool = True) -> ProbeState:
        self._require_session()
        self._run_gdb(["continue"])
        self._log_op("resume", payload={"resumed": True})
        return ProbeState(resumed=True, halted=False)

    def reset(
        self,
        kind: Literal["soft", "hard"] = "soft",
        halt_after: bool = False,
    ) -> ProbeState:
        self._require_session()
        cmds = [f"monitor reset {kind}"]
        if halt_after:
            cmds.append("monitor halt")
        self._run_gdb(cmds)
        self._log_op("reset", payload={"kind": kind, "halt_after": halt_after})
        return ProbeState(reset=True, halted_after=halt_after)

    def mem_read(
        self,
        addr: int,
        length: int,
        format: Literal["hex", "bytes"] = "hex",
    ) -> MemReadResult:
        self._require_session()
        words = max(1, (length + 3) // 4)
        output = self._run_gdb([f"x/{words}wx 0x{addr:08x}"])
        self._log_op("mem_read", payload={"addr": addr, "length": length})
        return MemReadResult(addr=addr, length=length, value=output.strip())

    def blackbox_export(self, out: Path) -> BlackboxExportResult:
        snapshot_at = datetime.now(tz=UTC)
        self._subprocess_run(
            [self._config.pyocd_bin, "pack", "export", "-o", str(out)],
            capture_output=True,
            text=True,
            check=False,
        )
        size = out.stat().st_size if out.exists() else 0
        self._log_op("blackbox_export", payload={"out": str(out)})
        return BlackboxExportResult(
            out=out, bytes_written=size, snapshot_at=snapshot_at
        )

    def itm_stream_start(
        self,
        ports: list[int],
        cpu_clock_hz: int | None = None,
        trace_clock_hz: int | None = None,
    ) -> ItmStreamHandle:
        handle = self._lanes.itm_swo.start(
            ports=ports,
            cpu_clock_hz=cpu_clock_hz,
            trace_clock_hz=trace_clock_hz,
        )
        self._log_op("itm_stream_start", lane="itm_swo", payload={"ports": ports})
        return handle

    def itm_stream_stop(self) -> ItmStreamSummary:
        summary = self._lanes.itm_swo.stop()
        self._log_op("itm_stream_stop", lane="itm_swo")
        return summary

    def lane_status(self) -> dict[str, LaneStatus]:
        return self._lanes.lane_status()

    def lane_release(self, lane: str) -> LaneStatus:
        result = self._lanes.lane_release(lane)
        self._log_op("lane_release", lane=lane, payload={"released": True})
        return result

    def lane_resume(self, lane: str) -> LaneStatus:
        result = self._lanes.lane_resume(lane)
        self._log_op("lane_resume", lane=lane, payload={"resumed": True})
        return result

    def recent_lines(self, since_seq: int = 0, limit: int = 100) -> list[LogLine]:
        with self._audit_lock:
            lines = [e for e in self._audit if e.seq >= since_seq]
        return lines[:limit]

    def session_start(self, **profile_kwargs: object) -> SessionStatus:
        result = self._sessions.start(**profile_kwargs)
        self._session_state = result.state
        return result

    def session_stop(self, force: bool = False) -> SessionStatus:
        result = self._sessions.stop(force=force)
        self._session_state = "stopped"
        return result

    def session_status(self) -> SessionStatus:
        return self._sessions.status()
