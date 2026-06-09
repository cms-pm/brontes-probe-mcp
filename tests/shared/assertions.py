# SPDX-License-Identifier: Apache-2.0
"""Shape validators — the bridge between mock and hardware test families.

Both the existing mock tests and the hardware tests import from here.
Functions assert response structure and types only; no hardware-specific
values are assumed so the same assertions pass in both contexts.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


def assert_session_status_shape(r: Any) -> None:
    assert r.state in {"stopped", "healthy", "unhealthy", "stale", "unknown"}
    assert isinstance(r.protocol_version, str) and r.protocol_version


def assert_probe_state_shape(r: Any) -> None:
    if r.halted is not None:
        assert isinstance(r.halted, bool)
    if r.pc is not None:
        assert isinstance(r.pc, int) and r.pc >= 0
    if r.resumed is not None:
        assert isinstance(r.resumed, bool)
    if r.reset is not None:
        assert isinstance(r.reset, bool)
    if r.halted_after is not None:
        assert isinstance(r.halted_after, bool)


def assert_mem_read_shape(r: Any, addr: int, length: int, fmt: str) -> None:
    assert r.addr == addr
    assert r.length == length
    assert r.format == fmt
    if fmt == "hex":
        assert isinstance(r.value, list)
        assert all(isinstance(v, str) and v.startswith(("0x", "0X")) for v in r.value)
    else:
        assert isinstance(r.value, str)
        base64.b64decode(r.value)  # raises if invalid


def assert_program_result_shape(r: Any) -> None:
    assert isinstance(r.programmed_bytes, int) and r.programmed_bytes > 0
    assert isinstance(r.duration_s, float) and r.duration_s > 0


def assert_blackbox_export_shape(r: Any, expected_out: Path) -> None:
    assert Path(r.out) == expected_out
    assert isinstance(r.bytes_written, int) and r.bytes_written > 0
    assert expected_out.exists()


def assert_itm_handle_shape(r: Any) -> None:
    assert isinstance(r.ports, list) and len(r.ports) > 0
    assert all(isinstance(p, int) for p in r.ports)
    if r.trace_clock_hz is not None:
        assert isinstance(r.trace_clock_hz, int) and r.trace_clock_hz > 0


def assert_lane_status_shape(r: Any, lane: str) -> None:
    assert r.lane == lane
    if r.released is not None:
        assert isinstance(r.released, bool)
    if r.resumed is not None:
        assert isinstance(r.resumed, bool)


def assert_log_line_shape(r: Any) -> None:
    assert isinstance(r.seq, int) and r.seq >= 0
    assert isinstance(r.method, str) and r.method
    assert isinstance(r.ok, bool)


def assert_error_shape(r: dict[str, Any], kind: str) -> None:
    assert "error" in r, f"expected error key, got: {list(r.keys())}"
    err = r["error"]
    assert err["kind"] == kind, f"expected kind={kind!r}, got {err['kind']!r}"
    assert isinstance(err["message"], str) and err["message"]
