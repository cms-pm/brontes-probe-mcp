# SPDX-License-Identifier: Apache-2.0
"""Phase 2 chunk 2.1.1 H1 — ITM/SWO capture + itm_stream_export.

Acceptance: SCN-2.1.1-ITM-EXPORT-EXISTS, SCN-2.1.1-ITM-RAW-ARTIFACT,
SCN-2.1.1-ITM-DECODED-ARTIFACT, SCN-2.1.1-ITM-OVERFLOW-COUNTER.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.itm import SwoSource, decode_software_packets
from brontes_probe_mcp.core.lanes import ItmSwoLane
from brontes_probe_mcp.core.models import ItmStreamExport, ItmStreamSummary


class FakeSwoSource:
    """Scripted byte source: hands out preloaded chunks then yields b''."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self._lock = threading.Lock()
        self.closed = False

    def read(self, max_bytes: int = 4096) -> bytes:
        with self._lock:
            if self._chunks:
                return self._chunks.pop(0)
        time.sleep(0.01)
        return b""

    def close(self) -> None:
        self.closed = True


def _swit_packet(port: int, payload: bytes) -> bytes:
    """Build a single SWIT (software) packet for port with payload (1/2/4 bytes)."""
    size = len(payload)
    size_code = {1: 0b01, 2: 0b10, 4: 0b11}[size]
    header = ((port & 0x1F) << 3) | size_code
    return bytes([header]) + payload


def _drain(source: FakeSwoSource, lane: ItmSwoLane, timeout: float = 1.0) -> None:
    """Wait until the lane has consumed all scripted chunks."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with source._lock:
            empty = not source._chunks
        if empty:
            return
        time.sleep(0.01)


# ── decoder unit tests ────────────────────────────────────────────────────────

def test_decode_single_swit_packet_port0_one_byte() -> None:
    buf = _swit_packet(0, b"\xab")
    records, count = decode_software_packets(buf)
    assert count == 1
    assert records == [
        {"port": 0, "timestamp_us": None, "data_hex": "ab"},
    ]


def test_decode_multiple_packets_mixed_sizes() -> None:
    buf = (
        _swit_packet(0, b"\xab")
        + _swit_packet(1, b"\xcd\xef")
        + _swit_packet(2, b"\xde\xad\xbe\xef")
    )
    records, count = decode_software_packets(buf)
    assert count == 3
    assert [r["port"] for r in records] == [0, 1, 2]
    assert [r["data_hex"] for r in records] == ["ab", "cdef", "deadbeef"]


def test_decode_skips_overflow_byte_but_continues() -> None:
    buf = _swit_packet(0, b"\x01") + b"\x70" + _swit_packet(0, b"\x02")
    records, count = decode_software_packets(buf)
    assert count == 2
    assert [r["data_hex"] for r in records] == ["01", "02"]


def test_port_filter_excludes_other_ports() -> None:
    buf = _swit_packet(0, b"\x01") + _swit_packet(1, b"\x02")
    records, count = decode_software_packets(buf, port_filter={0})
    assert count == 2
    assert len(records) == 1
    assert records[0]["port"] == 0


def test_decode_handles_partial_trailing_packet() -> None:
    # Header says 4-byte payload but only 2 bytes follow — must not raise.
    buf = bytes([(0 << 3) | 0b11, 0x01, 0x02])
    records, count = decode_software_packets(buf)
    assert count == 0
    assert records == []


# ── lane capture tests ────────────────────────────────────────────────────────

def test_lane_capture_records_bytes_and_packets() -> None:
    payload = _swit_packet(0, b"\xab") + _swit_packet(0, b"\xcd\xef")
    source = FakeSwoSource([payload])
    lane = ItmSwoLane(config=BrokerConfig())
    lane.start(ports=[0], _source=source)
    _drain(source, lane)
    summary = lane.stop()
    assert isinstance(summary, ItmStreamSummary)
    assert summary.bytes_captured == len(payload)
    assert summary.packet_count == 2
    assert summary.overflow_count == 0
    assert source.closed is True


def test_lane_overflow_counter_counts_0x70_bytes() -> None:
    payload = _swit_packet(0, b"\x01") + b"\x70\x70\x70" + _swit_packet(0, b"\x02")
    source = FakeSwoSource([payload])
    lane = ItmSwoLane(config=BrokerConfig())
    lane.start(ports=[0], _source=source)
    _drain(source, lane)
    summary = lane.stop()
    assert summary.overflow_count == 3
    assert summary.packet_count == 2


def test_lane_ring_buffer_truncates_at_max() -> None:
    config = BrokerConfig(itm_buffer_bytes=8)
    payload = _swit_packet(0, b"\xab") * 32  # 64 bytes total
    source = FakeSwoSource([payload])
    lane = ItmSwoLane(config=config)
    lane.start(ports=[0], _source=source)
    _drain(source, lane)
    summary = lane.stop()
    snapshot = lane.snapshot_bytes()
    assert summary.bytes_captured == 64
    assert len(snapshot) <= 8


# ── broker.itm_stream_export end-to-end ───────────────────────────────────────

@pytest.fixture()
def broker(tmp_path: Path) -> BrokerCore:
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    mock_popen = MagicMock(spec=subprocess.Popen)
    return BrokerCore(
        config=config,
        _subprocess_run=MagicMock(),
        _subprocess_popen=MagicMock(return_value=mock_popen),
    )


def test_itm_stream_export_writes_raw_and_decoded(
    broker: BrokerCore, tmp_path: Path
) -> None:
    payload = (
        _swit_packet(0, b"\xab")
        + _swit_packet(0, b"\xcd\xef")
        + _swit_packet(0, b"\xde\xad\xbe\xef")
    )
    source = FakeSwoSource([payload])
    broker._lanes.itm_swo.start(
        ports=[0], cpu_clock_hz=170_000_000, trace_clock_hz=2_000_000,
        _source=source,
    )
    _drain(source, broker._lanes.itm_swo)

    out = tmp_path / "itm-2.1.1.bin"
    export: Any = broker.itm_stream_export(out=out, decode=True)

    assert isinstance(export, ItmStreamExport)
    assert export.raw_artifact_path == Path(f"{out}.raw.bin")
    assert export.decoded_artifact_path == Path(f"{out}.decoded.jsonl")
    assert export.bytes_written == len(payload)
    assert export.packet_count == 3
    assert export.cpu_clock_hz == 170_000_000
    assert export.trace_clock_hz == 2_000_000

    raw_bytes = export.raw_artifact_path.read_bytes()
    assert raw_bytes == payload

    assert export.decoded_artifact_path is not None
    lines = [
        json.loads(line)
        for line in export.decoded_artifact_path.read_text().splitlines()
        if line
    ]
    assert len(lines) == 3
    assert all(r["port"] == 0 for r in lines)
    assert lines[0]["data_hex"] == "ab"


def test_itm_stream_export_decode_false_skips_jsonl(
    broker: BrokerCore, tmp_path: Path
) -> None:
    payload = _swit_packet(0, b"\x01")
    source = FakeSwoSource([payload])
    broker._lanes.itm_swo.start(ports=[0], _source=source)
    _drain(source, broker._lanes.itm_swo)
    out = tmp_path / "no-decode.bin"
    export = broker.itm_stream_export(out=out, decode=False)
    assert export.decoded_artifact_path is None
    assert export.raw_artifact_path.exists()
    assert not (tmp_path / "no-decode.bin.decoded.jsonl").exists()


def test_itm_stream_stop_summary_echoes_artifact_path_after_export(
    broker: BrokerCore, tmp_path: Path
) -> None:
    payload = _swit_packet(0, b"\x01")
    source = FakeSwoSource([payload])
    broker._lanes.itm_swo.start(ports=[0], _source=source)
    _drain(source, broker._lanes.itm_swo)
    out = tmp_path / "with-export.bin"
    broker.itm_stream_export(out=out, decode=False)
    summary = broker.itm_stream_stop()
    assert summary.artifact_path == Path(f"{out}.raw.bin")
    assert summary.bytes_captured == len(payload)
    assert summary.packet_count == 1


def test_default_itm_stream_start_uses_null_source(broker: BrokerCore) -> None:
    """When no _source is injected and SWV is disabled, capture yields zero bytes."""
    broker.itm_stream_start(ports=[0])
    time.sleep(0.05)
    summary = broker.itm_stream_stop()
    assert summary.stopped is True
    assert summary.bytes_captured == 0
    assert summary.packet_count == 0
    assert summary.overflow_count == 0
