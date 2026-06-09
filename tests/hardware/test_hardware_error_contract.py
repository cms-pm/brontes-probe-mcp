# SPDX-License-Identifier: Apache-2.0
"""Hardware tests — error contract with real hardware responses."""
from __future__ import annotations

import json
import socket
from typing import Any

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.transports import _rpc
from tests.shared.assertions import assert_error_shape

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


def _tcp_call(
    port: int,
    token: str,
    method: str,
    kwargs: dict[str, Any] | None = None,
) -> Any:
    payload = json.dumps({"method": method, "kwargs": kwargs or {}})
    with socket.create_connection(("127.0.0.1", port), timeout=10.0) as s:
        sf = s.makefile("rwb")
        sf.write((token + "\n").encode())
        sf.flush()
        sf.write((payload + "\n").encode())
        sf.flush()
        response = sf.readline()
    return json.loads(response.strip())


# ── session_required errors ────────────────────────────────────────────────────

def test_session_required_halt_via_dispatch(hil_broker: BrokerCore) -> None:
    result = _rpc.dispatch(hil_broker, "halt", {})
    assert_error_shape(result, "session_required")


def test_session_required_mem_read_via_dispatch(hil_broker: BrokerCore) -> None:
    result = _rpc.dispatch(hil_broker, "mem_read", {"addr": 0x20000000, "length": 4})
    assert_error_shape(result, "session_required")


def test_session_required_reset_via_dispatch(hil_broker: BrokerCore) -> None:
    result = _rpc.dispatch(hil_broker, "reset", {})
    assert_error_shape(result, "session_required")


# ── method_unknown errors ─────────────────────────────────────────────────────

def test_method_unknown_via_socket(hil_socket_server: Any) -> None:
    _srv, sock_path = hil_socket_server
    result = _socket_call(sock_path, "does_not_exist")
    assert_error_shape(result, "method_unknown")


def test_method_unknown_via_tcp(hil_tcp_server: Any) -> None:
    _srv, port, token = hil_tcp_server
    result = _tcp_call(port, token, "does_not_exist")
    assert_error_shape(result, "method_unknown")


def test_method_unknown_empty_name_via_socket(hil_socket_server: Any) -> None:
    _srv, sock_path = hil_socket_server
    result = _socket_call(sock_path, "")
    assert_error_shape(result, "method_unknown")


# ── gdb error on bad address (requires session) ───────────────────────────────

def test_gdb_error_on_bad_address(hil_session: Any) -> None:
    # 0xDEADBEEF is an unmapped address — GDB will error
    result = _rpc.dispatch(
        hil_session, "mem_read", {"addr": 0xDEADBEEF, "length": 4}
    )
    # May return a broker_internal_error or session_required; must be an error
    assert "error" in result
