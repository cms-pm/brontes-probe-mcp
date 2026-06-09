# SPDX-License-Identifier: Apache-2.0
"""Hardware tests — audit log (recent_lines) with real operations."""
from __future__ import annotations

import json
import socket
from typing import Any

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.transports import _rpc
from tests.shared.assertions import assert_log_line_shape

pytestmark = pytest.mark.hardware


def _socket_call(
    sock_path: str, method: str, kwargs: dict[str, Any] | None = None
) -> Any:
    payload = json.dumps({"method": method, "kwargs": kwargs or {}})
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(10.0)
        s.connect(sock_path)
        s.sendall((payload + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    return json.loads(data.strip())


def test_recent_lines_empty_initially(hil_broker: BrokerCore) -> None:
    lines = hil_broker.recent_lines()
    assert lines == []


def test_recent_lines_populated_after_ops(hil_session: Any) -> None:
    hil_session.halt()
    hil_session.resume()
    lines = hil_session.recent_lines()
    assert len(lines) >= 2
    for line in lines:
        assert_log_line_shape(line)


def test_recent_lines_method_names(hil_session: Any) -> None:
    hil_session.halt()
    hil_session.resume()
    hil_session.reset()
    lines = hil_session.recent_lines()
    methods = {line.method for line in lines}
    assert "halt" in methods
    assert "resume" in methods
    assert "reset" in methods


def test_recent_lines_ok_true_for_success(hil_session: Any) -> None:
    hil_session.halt()
    lines = hil_session.recent_lines()
    halt_lines = [ln for ln in lines if ln.method == "halt"]
    assert len(halt_lines) >= 1
    assert all(ln.ok is True for ln in halt_lines)


def test_recent_lines_since_seq(hil_session: Any) -> None:
    for _ in range(5):
        hil_session.halt()
        hil_session.resume()
    all_lines = hil_session.recent_lines()
    assert len(all_lines) >= 5
    mid_seq = all_lines[3].seq
    since_lines = hil_session.recent_lines(since_seq=mid_seq + 1)
    assert all(ln.seq >= mid_seq + 1 for ln in since_lines)


def test_recent_lines_limit(hil_session: Any) -> None:
    for _ in range(10):
        hil_session.halt()
    limited = hil_session.recent_lines(limit=3)
    assert len(limited) <= 3


def test_next_seq_field_via_socket(
    hil_session: Any, hil_socket_server: Any
) -> None:
    _srv, sock_path = hil_socket_server
    hil_session.halt()
    result = _socket_call(sock_path, "recent_lines")
    assert "next_seq" in result
    assert "lines" in result
    lines = result["lines"]
    if lines:
        max_seq = max(ln["seq"] for ln in lines)
        assert result["next_seq"] == max_seq + 1


def test_recent_lines_seq_monotonic(hil_session: Any) -> None:
    hil_session.halt()
    hil_session.resume()
    hil_session.reset()
    lines = hil_session.recent_lines()
    seqs = [ln.seq for ln in lines]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_audit_via_rpc_dispatch(hil_session: Any) -> None:
    hil_session.halt()
    result = _rpc.dispatch(hil_session, "recent_lines", {})
    assert "lines" in result
    assert "next_seq" in result
    assert isinstance(result["next_seq"], int)
