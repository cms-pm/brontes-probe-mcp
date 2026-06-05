# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import tempfile
import threading
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports.socket import _UnixServer
from brontes_probe_mcp.transports.stdio import _call_handler
from brontes_probe_mcp.transports.tcp import _TcpServer

_TEST_TOKEN = "parity-test-token-abc"


def _completed(stdout: str = "", returncode: int = 0) -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@pytest.fixture()
def parity_broker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BrokerCore:
    mock_run = MagicMock(return_value=_completed())
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 12345
    mock_popen = MagicMock(return_value=proc)
    config = BrokerConfig(log_dir=str(tmp_path / "logs"))
    broker = BrokerCore(
        config=config,
        _subprocess_run=mock_run,
        _subprocess_popen=mock_popen,
    )
    monkeypatch.setattr(broker._sessions, "_tcp_ready", lambda *a, **kw: False)
    broker._session_state = "healthy"
    return broker


@pytest.fixture()
def socket_server(parity_broker: BrokerCore) -> Any:
    # Use /tmp directly to stay under macOS AF_UNIX 104-char path limit
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        sock_path = str(Path(td) / "p.sock")
        config = BrokerConfig(socket_path=sock_path)
        srv = _UnixServer(parity_broker, config)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        yield parity_broker, sock_path
        srv.shutdown()
        t.join(timeout=2)


@pytest.fixture()
def tcp_server(parity_broker: BrokerCore) -> Any:
    config = BrokerConfig(tcp_host="127.0.0.1", tcp_port=0, token=_TEST_TOKEN)
    srv = _TcpServer(parity_broker, config, _TEST_TOKEN)
    port: int = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield parity_broker, port, _TEST_TOKEN
    srv.shutdown()
    t.join(timeout=2)


def via_socket(sock_path: str, method: str, kwargs: dict[str, Any]) -> Any:
    payload = json.dumps({"method": method, "kwargs": kwargs})
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(5.0)
        s.connect(sock_path)
        s.sendall((payload + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    return json.loads(data.strip())


def via_tcp(port: int, token: str, method: str, kwargs: dict[str, Any]) -> Any:
    payload = json.dumps({"method": method, "kwargs": kwargs})
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as s:
        sf = s.makefile("rwb")
        sf.write((token + "\n").encode())
        sf.flush()
        sf.write((payload + "\n").encode())
        sf.flush()
        response = sf.readline()
    return json.loads(response.strip())


def via_stdio(broker: BrokerCore, tool_name: str, kwargs: dict[str, Any]) -> Any:
    result_json = asyncio.run(_call_handler(broker, tool_name, kwargs))
    return json.loads(result_json)


def _stable_keys(d: dict[str, Any]) -> dict[str, Any]:
    """Strip timing-sensitive fields for structural comparison."""
    return {k: v for k, v in d.items() if k not in {"duration_s", "snapshot_at"}}


_PARITY_TABLE: list[tuple[str, str, dict[str, Any], str]] = [
    ("session_status", "session_status", {}, ""),
    ("session_stop", "session_stop", {}, ""),
    ("session_start", "session_start", {"target": "test_target"}, "unhealthy OK"),
    ("probe_halt", "halt", {}, ""),
    ("probe_resume", "resume", {}, ""),
    ("probe_reset", "reset", {}, ""),
    ("probe_mem_read", "mem_read", {"addr": 0x20000000, "length": 4}, ""),
    ("itm_stream_start", "itm_stream_start", {"ports": [0]}, ""),
    ("itm_stream_stop", "itm_stream_stop", {}, ""),
    ("lane_status", "lane_status", {}, ""),
    ("lane_release", "lane_release", {"lane": "swd"}, ""),
    ("lane_resume", "lane_resume", {"lane": "swd"}, ""),
    ("recent_lines", "recent_lines", {}, ""),
]


@pytest.mark.parametrize(
    "stdio_name,socket_method,kwargs,note",
    _PARITY_TABLE,
    ids=[row[0] for row in _PARITY_TABLE],
)
def test_parity(
    stdio_name: str,
    socket_method: str,
    kwargs: dict[str, Any],
    note: str,
    socket_server: Any,
    tcp_server: Any,
) -> None:
    broker, sock_path = socket_server
    _broker_tcp, port, token = tcp_server

    r_socket = via_socket(sock_path, socket_method, kwargs)
    r_tcp = via_tcp(port, token, socket_method, kwargs)
    r_stdio = via_stdio(broker, stdio_name, kwargs)

    assert r_socket == r_tcp, (
        f"socket vs tcp mismatch for {stdio_name!r}: {r_socket!r} != {r_tcp!r}"
    )
    assert r_socket == r_stdio, (
        f"socket vs stdio mismatch for {stdio_name!r}: {r_socket!r} != {r_stdio!r}"
    )


_PARITY_PATH_TABLE: list[tuple[str, str, str]] = [
    ("probe_program", "program", "elf"),
    ("probe_flash", "flash", "alias"),
    ("probe_blackbox_export", "blackbox_export", ""),
]


@pytest.mark.parametrize(
    "stdio_name,socket_method,note",
    _PARITY_PATH_TABLE,
    ids=[row[0] for row in _PARITY_PATH_TABLE],
)
def test_parity_path_args(
    stdio_name: str,
    socket_method: str,
    note: str,
    socket_server: Any,
    tcp_server: Any,
    tmp_path: Path,
) -> None:
    broker, sock_path = socket_server
    _broker_tcp, port, token = tcp_server

    elf_path = tmp_path / "fw.elf"
    elf_path.write_bytes(b"\x00" * 64)
    out_path = tmp_path / "export.bin"
    out_path.write_bytes(b"\xde\xad" * 4)

    kwargs: dict[str, Any]
    if stdio_name in ("probe_program", "probe_flash"):
        kwargs = {"artifact": str(elf_path)}
    else:
        kwargs = {"out": str(out_path)}

    r_socket = _stable_keys(via_socket(sock_path, socket_method, kwargs))
    r_tcp = _stable_keys(via_tcp(port, token, socket_method, kwargs))
    r_stdio = _stable_keys(via_stdio(broker, stdio_name, kwargs))

    assert r_socket == r_tcp, (
        f"socket vs tcp mismatch for {stdio_name!r}: {r_socket!r} != {r_tcp!r}"
    )
    assert r_socket == r_stdio, (
        f"socket vs stdio mismatch for {stdio_name!r}: {r_socket!r} != {r_stdio!r}"
    )


def test_scn_1_2_verb_alias(socket_server: Any) -> None:
    """SCN-1.2-VERB-ALIAS: flash and program return identical JSON via socket."""
    _broker, sock_path = socket_server

    elf_path = Path(sock_path).parent / "fw.elf"
    elf_path.write_bytes(b"\x00" * 64)

    r_program = via_socket(sock_path, "program", {"artifact": str(elf_path)})
    r_flash = via_socket(sock_path, "flash", {"artifact": str(elf_path)})

    # Both should succeed (have programmed_bytes) and be structurally identical
    # duration_s will differ slightly, so compare structural fields
    assert "programmed_bytes" in r_program
    assert "programmed_bytes" in r_flash
    assert r_program["programmed_bytes"] == r_flash["programmed_bytes"]
    assert r_program.get("format") == r_flash.get("format")
    assert r_program.get("halted") == r_flash.get("halted")
