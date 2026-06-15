# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.itm import (
    NullSwoSource,
    PyocdSwvTcpSource,
    SwoSource,
    count_overflow_bytes,
    decode_software_packets,
)
from brontes_probe_mcp.core.models import ItmStreamHandle, ItmStreamSummary, LaneStatus

SwoSourceFactory = Callable[[], SwoSource]


def _default_source_factory(config: BrokerConfig | None) -> SwoSourceFactory:
    """Default factory: connect to pyocd's SWV TCP port when enabled, else null.

    Returns a no-arg callable so the lane can request a fresh source per
    capture session without leaking sockets across start/stop cycles.
    """
    if config is None or not config.enable_swv:
        return NullSwoSource
    host = config.tcp_host
    # pyocd gdbserver SWV channel default: gdb_port + 110 (3333 → 3443).
    # Kept as a derived constant rather than a separate config knob until
    # there's a concrete need to retune.
    swv_port = config.gdb_port + 110
    return lambda: PyocdSwvTcpSource(host=host, port=swv_port)


class ItmSwoLane:
    """ITM/SWO capture lane.

    A background daemon thread drains the configured SwoSource into a
    bounded ring buffer. On stop(), the lane returns counters and the
    most recent buffer contents are exposed via snapshot_bytes() for
    BrokerCore.itm_stream_export() to write out.
    """

    def __init__(
        self,
        config: BrokerConfig | None = None,
        source_factory: SwoSourceFactory | None = None,
    ) -> None:
        self._config = config
        self._source_factory: SwoSourceFactory = (
            source_factory
            if source_factory is not None
            else _default_source_factory(config)
        )
        self._buffer_max: int = (
            config.itm_buffer_bytes if config is not None else 1024 * 1024
        )
        self._lock = threading.Lock()
        self._active = False
        self._ports: list[int] = []
        self._cpu_clock_hz: int | None = None
        self._trace_clock_hz: int | None = None
        self._stop_event = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._source: SwoSource | None = None
        self._buffer: bytearray = bytearray()
        self._bytes_captured: int = 0
        self._overflow_count: int = 0
        self._export_artifact: Path | None = None

    def start(
        self,
        ports: list[int],
        cpu_clock_hz: int | None = None,
        trace_clock_hz: int | None = None,
        _source: SwoSource | None = None,
    ) -> ItmStreamHandle:
        """Begin capture. Pass _source to inject a specific SwoSource (tests/HIL)."""
        with self._lock:
            self._active = True
            self._ports = list(ports)
            self._cpu_clock_hz = cpu_clock_hz
            self._trace_clock_hz = trace_clock_hz
            self._buffer = bytearray()
            self._bytes_captured = 0
            self._overflow_count = 0
            self._export_artifact = None
            self._stop_event.clear()
            self._source = _source if _source is not None else self._source_factory()
            thread = threading.Thread(
                target=self._reader_loop, name="itm-swo-reader", daemon=True
            )
            self._reader_thread = thread
        thread.start()
        return ItmStreamHandle(ports=list(ports), trace_clock_hz=trace_clock_hz)

    def _reader_loop(self) -> None:
        source = self._source
        if source is None:
            return
        while not self._stop_event.is_set():
            chunk = source.read(4096)
            if not chunk:
                continue
            with self._lock:
                self._bytes_captured += len(chunk)
                self._overflow_count += count_overflow_bytes(chunk)
                self._buffer.extend(chunk)
                excess = len(self._buffer) - self._buffer_max
                if excess > 0:
                    del self._buffer[:excess]

    def stop(self) -> ItmStreamSummary:
        with self._lock:
            self._active = False
            self._stop_event.set()
        thread = self._reader_thread
        if thread is not None:
            thread.join(timeout=1.0)
        source = self._source
        if source is not None:
            source.close()
        with self._lock:
            buf = bytes(self._buffer)
            bytes_captured = self._bytes_captured
            overflow = self._overflow_count
            artifact = self._export_artifact
            port_filter: set[int] | None = (
                set(self._ports) if self._ports else None
            )
            self._reader_thread = None
            self._source = None
        _, packet_count = decode_software_packets(buf, port_filter=port_filter)
        return ItmStreamSummary(
            stopped=True,
            bytes_captured=bytes_captured,
            packet_count=packet_count,
            overflow_count=overflow,
            artifact_path=artifact,
        )

    def snapshot_bytes(self) -> bytes:
        with self._lock:
            return bytes(self._buffer)

    def context(self) -> tuple[list[int], int | None, int | None]:
        with self._lock:
            return list(self._ports), self._cpu_clock_hz, self._trace_clock_hz

    def set_export_artifact(self, path: Path) -> None:
        with self._lock:
            self._export_artifact = path


class LaneSupervisor:
    def __init__(self, config: BrokerConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self.itm_swo = ItmSwoLane(config=config)
        # True = normal/active; False = released
        self._lane_states: dict[str, bool] = dict.fromkeys(config.lanes, True)

    def _require_lane(self, lane: str) -> None:
        if lane not in self._lane_states:
            raise ValueError(
                f"unknown lane {lane!r}; configured lanes: {list(self._lane_states)}"
            )

    def lane_status(self) -> dict[str, LaneStatus]:
        with self._lock:
            snapshot = dict(self._lane_states)
        return {
            lane: LaneStatus(lane=lane, released=not active, resumed=active)
            for lane, active in snapshot.items()
        }

    def lane_release(self, lane: str) -> LaneStatus:
        self._require_lane(lane)
        with self._lock:
            self._lane_states[lane] = False
        return LaneStatus(lane=lane, released=True, resumed=False)

    def lane_resume(self, lane: str) -> LaneStatus:
        self._require_lane(lane)
        with self._lock:
            self._lane_states[lane] = True
        return LaneStatus(lane=lane, released=False, resumed=True)
