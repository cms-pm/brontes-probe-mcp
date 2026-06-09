# SPDX-License-Identifier: Apache-2.0
"""Hardware tests — all three transports vs real hardware."""
from __future__ import annotations

import json
import socket
import sys
from typing import Any

import pytest

from brontes_probe_mcp.transports import _rpc
from tests.shared.assertions import assert_session_status_shape

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


# ── session_status via each transport ────────────────────────────────────────

def test_socket_session_status(hil_socket_server: Any) -> None:
    _srv, sock_path = hil_socket_server
    result = _socket_call(sock_path, "session_status")
    assert "state" in result


def test_tcp_session_status(hil_tcp_server: Any) -> None:
    _srv, port, token = hil_tcp_server
    result = _tcp_call(port, token, "session_status")
    assert "state" in result


def test_rpc_dispatch_session_status(hil_broker: Any) -> None:
    result = _rpc.dispatch(hil_broker, "session_status", {})
    assert_session_status_shape(result)


# ── halt/resume via transports (requires active session) ─────────────────────

def test_socket_halt(hil_session: Any, hil_socket_server: Any) -> None:
    _srv, sock_path = hil_socket_server
    result = _socket_call(sock_path, "halt")
    assert result.get("halted") is True


def test_tcp_halt(hil_session: Any, hil_tcp_server: Any) -> None:
    _srv, port, token = hil_tcp_server
    result = _tcp_call(port, token, "halt")
    assert result.get("halted") is True


# ── transport parity ──────────────────────────────────────────────────────────

def test_parity_session_status(
    hil_broker: Any,
    hil_socket_server: Any,
    hil_tcp_server: Any,
) -> None:
    _srv_s, sock_path = hil_socket_server
    _srv_t, port, token = hil_tcp_server

    via_socket = _socket_call(sock_path, "session_status")
    via_tcp = _tcp_call(port, token, "session_status")
    via_dispatch = _rpc.dispatch(hil_broker, "session_status", {})

    dispatch_dict = via_dispatch.model_dump(mode="json")
    assert via_socket["state"] == dispatch_dict["state"]
    assert via_tcp["state"] == dispatch_dict["state"]
    assert via_socket["protocol_version"] == dispatch_dict["protocol_version"]
    assert via_tcp["protocol_version"] == dispatch_dict["protocol_version"]


def test_parity_mem_read(
    hil_session: Any,
    hil_sram_addr: int,
    hil_socket_server: Any,
    hil_tcp_server: Any,
) -> None:
    _srv_s, sock_path = hil_socket_server
    _srv_t, port, token = hil_tcp_server

    kwargs = {"addr": hil_sram_addr, "length": 4, "format": "hex"}
    via_socket = _socket_call(sock_path, "mem_read", kwargs)
    via_tcp = _tcp_call(port, token, "mem_read", kwargs)
    via_dispatch = _rpc.dispatch(hil_session, "mem_read", kwargs)

    dispatch_dict = via_dispatch.model_dump(mode="json")
    assert via_socket["value"] == dispatch_dict["value"]
    assert via_tcp["value"] == dispatch_dict["value"]


# ── auth edge cases ───────────────────────────────────────────────────────────

def test_tcp_wrong_token(hil_tcp_server: Any) -> None:
    _srv, port, _token = hil_tcp_server
    response = b""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5.0) as s:
            sf = s.makefile("rwb")
            sf.write(b"bad-token\n")
            sf.flush()
            sf.write(b'{"method": "session_status", "kwargs": {}}\n')
            sf.flush()
            response = sf.readline()
    except ConnectionResetError:
        response = b""
    assert response == b""


@pytest.mark.skipif(sys.platform != "linux", reason="SO_PEERCRED is Linux-only")
def test_socket_peercred_valid_uid(hil_socket_server: Any) -> None:
    _srv, sock_path = hil_socket_server
    # Valid UID (same process) — request should succeed
    result = _socket_call(sock_path, "session_status")
    assert "state" in result


# ── verb alias ────────────────────────────────────────────────────────────────

def test_verb_alias_flash_via_socket(
    hil_session: Any, hil_elf: Any, hil_socket_server: Any
) -> None:
    _srv, sock_path = hil_socket_server
    result = _socket_call(
        sock_path, "flash", {"artifact": str(hil_elf)}
    )
    assert "programmed_bytes" in result
    assert result["programmed_bytes"] > 0
