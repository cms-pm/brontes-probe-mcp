# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.transports import _rpc

_TOOLS: list[types.Tool] = [
    types.Tool(
        name="session_start",
        description="Start a probe session",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "probe_uid": {"type": "string"},
            },
        },
    ),
    types.Tool(
        name="session_stop",
        description="Stop the current probe session",
        inputSchema={
            "type": "object",
            "properties": {
                "force": {"type": "boolean"},
            },
        },
    ),
    types.Tool(
        name="session_status",
        description="Get current session status",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="probe_program",
        description="Flash firmware to the target device",
        inputSchema={
            "type": "object",
            "properties": {
                "artifact": {"type": "string"},
                "format": {"type": "string", "enum": ["elf", "bin", "hex"]},
                "address": {"type": "integer"},
                "halt_after": {"type": "boolean"},
                "reset_after": {"type": "boolean"},
            },
            "required": ["artifact"],
        },
    ),
    types.Tool(
        name="probe_flash",
        description="Flash firmware to the target device (alias for probe_program)",
        inputSchema={
            "type": "object",
            "properties": {
                "artifact": {"type": "string"},
                "format": {"type": "string", "enum": ["elf", "bin", "hex"]},
                "address": {"type": "integer"},
                "halt_after": {"type": "boolean"},
                "reset_after": {"type": "boolean"},
            },
            "required": ["artifact"],
        },
    ),
    types.Tool(
        name="probe_halt",
        description="Halt the target CPU",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="probe_resume",
        description="Resume the target CPU",
        inputSchema={
            "type": "object",
            "properties": {
                "disconnect_gdb": {"type": "boolean"},
            },
        },
    ),
    types.Tool(
        name="probe_reset",
        description="Reset the target device",
        inputSchema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["soft", "hard"]},
                "halt_after": {"type": "boolean"},
            },
        },
    ),
    types.Tool(
        name="probe_mem_read",
        description="Read target memory",
        inputSchema={
            "type": "object",
            "properties": {
                "addr": {"type": "integer"},
                "length": {"type": "integer"},
                "format": {"type": "string", "enum": ["hex", "bytes"]},
            },
            "required": ["addr", "length"],
        },
    ),
    types.Tool(
        name="probe_blackbox_export",
        description="Export a blackbox snapshot",
        inputSchema={
            "type": "object",
            "properties": {
                "out": {"type": "string"},
            },
            "required": ["out"],
        },
    ),
    types.Tool(
        name="itm_stream_start",
        description="Start ITM/SWO trace streaming",
        inputSchema={
            "type": "object",
            "properties": {
                "ports": {"type": "array", "items": {"type": "integer"}},
                "cpu_clock_hz": {"type": "integer"},
                "trace_clock_hz": {"type": "integer"},
            },
            "required": ["ports"],
        },
    ),
    types.Tool(
        name="itm_stream_stop",
        description="Stop ITM/SWO trace streaming",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="lane_status",
        description="Get status of all lanes",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="lane_release",
        description="Release a lane",
        inputSchema={
            "type": "object",
            "properties": {
                "lane": {"type": "string"},
            },
            "required": ["lane"],
        },
    ),
    types.Tool(
        name="lane_resume",
        description="Resume a lane",
        inputSchema={
            "type": "object",
            "properties": {
                "lane": {"type": "string"},
            },
            "required": ["lane"],
        },
    ),
    types.Tool(
        name="recent_lines",
        description="Get recent audit log lines",
        inputSchema={
            "type": "object",
            "properties": {
                "since_seq": {"type": "integer"},
                "limit": {"type": "integer"},
            },
        },
    ),
]

# Map stdio tool names → broker method names
_STDIO_TO_BROKER: dict[str, str] = {
    "session_start": "session_start",
    "session_stop": "session_stop",
    "session_status": "session_status",
    "probe_program": "program",
    "probe_flash": "program",  # permanent alias
    "probe_halt": "halt",
    "probe_resume": "resume",
    "probe_reset": "reset",
    "probe_mem_read": "mem_read",
    "probe_blackbox_export": "blackbox_export",
    "itm_stream_start": "itm_stream_start",
    "itm_stream_stop": "itm_stream_stop",
    "lane_status": "lane_status",
    "lane_release": "lane_release",
    "lane_resume": "lane_resume",
    "recent_lines": "recent_lines",
}

# Path-coercion: tool name → kwarg keys that need Path conversion
_PATH_TOOL_KWARGS: dict[str, frozenset[str]] = {
    "probe_program": frozenset({"artifact"}),
    "probe_flash": frozenset({"artifact"}),
    "probe_blackbox_export": frozenset({"out"}),
}


async def _call_handler(
    broker: BrokerCore,
    name: str,
    arguments: dict[str, Any],
) -> str:
    """Dispatch a tool call and return the serialized JSON result string."""
    broker_method = _STDIO_TO_BROKER.get(name)
    if broker_method is None:
        return _rpc.error_response(
            "method_unknown",
            f"unknown tool {name!r}",
        )

    kwargs = dict(arguments)

    path_keys = _PATH_TOOL_KWARGS.get(name, frozenset())
    for key in path_keys:
        if key in kwargs and not isinstance(kwargs[key], Path):
            kwargs[key] = Path(str(kwargs[key]))

    try:
        fn = getattr(broker, broker_method, None)
        if fn is None:
            return _rpc.error_response(
                "method_unknown", f"unknown method {broker_method!r}"
            )

        result = fn(**kwargs)

        if broker_method == "recent_lines":
            lines = result if isinstance(result, list) else []
            seqs = [
                entry.seq
                for entry in lines
                if hasattr(entry, "seq") and isinstance(entry.seq, int)
            ]
            since_seq: int = int(kwargs.get("since_seq", 0))
            next_seq = max(seqs) + 1 if seqs else since_seq
            return _rpc.serialize(
                {"lines": _rpc._to_json_obj(lines), "next_seq": next_seq}
            )

        return _rpc.serialize(result)

    except Exception as exc:
        return _rpc.error_response("broker_internal_error", str(exc))


async def _serve_async(broker: BrokerCore) -> None:
    server = Server("brontes-probe-mcp")

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        return _TOOLS

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> types.CallToolResult:
        args: dict[str, Any] = arguments if arguments is not None else {}
        result_json = await _call_handler(broker, name, args)
        parsed: Any = json.loads(result_json)
        is_error = isinstance(parsed, dict) and "error" in parsed
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result_json)],
            isError=is_error,
        )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run(broker: BrokerCore) -> None:
    """Run the stdio MCP transport (blocking)."""
    asyncio.run(_serve_async(broker))
