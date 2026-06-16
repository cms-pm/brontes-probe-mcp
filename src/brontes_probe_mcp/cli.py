# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from brontes_probe_mcp import __version__
from brontes_probe_mcp.core.config import BrokerConfig


def _probe_boards(pyocd_bin: str) -> list[dict[str, object]]:
    """Return the boards list from `pyocd json --probes`, or [] on any error."""
    try:
        result = subprocess.run(
            [pyocd_bin, "json", "--probes"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        boards = data.get("boards", [])
        return boards if isinstance(boards, list) else []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []


def _cmd_probe_agent_start(args: argparse.Namespace) -> None:
    from brontes_probe_mcp.core.session import SessionManager

    config = BrokerConfig(log_dir=args.state_dir)
    mgr = SessionManager(config=config)

    target = args.target
    if not target:
        boards = _probe_boards(config.pyocd_bin)
        count = len(boards)
        if count == 1 and boards[0].get("target"):
            target = str(boards[0]["target"])
        else:
            if count == 0:
                print("No debug probes found. Check USB connection.", file=sys.stderr)
            elif count == 1:
                print(
                    "Probe found but target could not be auto-detected. "
                    "Specify --target <target> (e.g. stm32g474).",
                    file=sys.stderr,
                )
            else:
                print(
                    f"{count} probes found. Specify --target and --probe-uid.",
                    file=sys.stderr,
                )
            sys.exit(1)

    kwargs: dict[str, object] = {"target": target}
    if args.probe_uid:
        kwargs["probe_uid"] = args.probe_uid
    if args.port:
        kwargs["gdb_port"] = args.port
    if args.frequency_hz:
        kwargs["frequency_hz"] = args.frequency_hz
    if args.pack:
        kwargs["pack"] = args.pack

    result = mgr.start(profile="agent", **kwargs)
    print(json.dumps({"state": result.state, "target": result.target}))
    if result.state != "healthy":
        sys.exit(1)


def _cmd_probe_agent_stop(args: argparse.Namespace) -> None:
    from brontes_probe_mcp.core.session import SessionManager

    config = BrokerConfig(log_dir=args.state_dir)
    mgr = SessionManager(config=config)
    result = mgr.stop(force=args.force, profile="agent")
    print(json.dumps({"state": result.state}))


def _cmd_call(args: argparse.Namespace) -> None:
    """Send one JSON-RPC envelope over the Unix socket transport and print the reply.

    Exit code 0 on a non-error response, 1 on an error envelope or transport
    failure, 2 on invalid `--json` input.
    """
    import socket as _socket

    config = BrokerConfig()
    sock_path = args.socket or config.socket_path

    if args.json:
        try:
            parsed_kwargs = json.loads(args.json)
        except json.JSONDecodeError as exc:
            print(f"Invalid --json payload: {exc}", file=sys.stderr)
            sys.exit(2)
        if not isinstance(parsed_kwargs, dict):
            print("--json must decode to a JSON object", file=sys.stderr)
            sys.exit(2)
        kwargs: dict[str, object] = parsed_kwargs
    else:
        kwargs = {}

    envelope = json.dumps({"method": args.method, "kwargs": kwargs})

    try:
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
            s.settimeout(args.timeout)
            s.connect(sock_path)
            s.sendall((envelope + "\n").encode())
            buf = bytearray()
            while not buf.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf.extend(chunk)
    except OSError as exc:
        print(f"call failed: {exc}", file=sys.stderr)
        sys.exit(1)

    response = buf.decode(errors="replace").strip()
    print(response)

    try:
        parsed = json.loads(response) if response else None
    except json.JSONDecodeError:
        sys.exit(1)

    if isinstance(parsed, dict) and "error" in parsed:
        sys.exit(1)


def _cmd_probe_agent_status(args: argparse.Namespace) -> None:
    from brontes_probe_mcp.core.session import SessionManager

    config = BrokerConfig(log_dir=args.state_dir)
    mgr = SessionManager(config=config)
    result = mgr.status(profile="agent")
    print(json.dumps({"state": result.state, "target": result.target}))
    if result.state not in ("healthy",):
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="brontes-probe-mcp-cli",
        description="Brontes probe-broker MCP — operations CLI",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"brontes-probe-mcp {__version__}",
    )
    parser.add_argument(
        "--config-dump",
        action="store_true",
        help="Print resolved BrokerConfig as JSON and exit",
    )

    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start transport servers")
    serve_parser.add_argument(
        "--transports",
        metavar="CSV",
        help="Comma-separated transports (overrides config)",
        dest="serve_transports",
    )

    subparsers.add_parser(
        "session-unlock",
        help="Force-remove a stale session operation lock",
    )

    # ── call subcommand (generic RPC envelope) ────────────────────────────────
    call_parser = subparsers.add_parser(
        "call",
        help="Send one JSON-RPC envelope to a running broker over Unix socket",
    )
    call_parser.add_argument(
        "method",
        help="Broker method name (e.g. session_status, halt, mem_read)",
    )
    call_parser.add_argument(
        "--json",
        dest="json",
        default=None,
        metavar="STR",
        help='kwargs as a JSON object string (e.g. \'{"addr":536870912,"length":4}\')',
    )
    call_parser.add_argument(
        "--socket",
        default=None,
        metavar="PATH",
        help="Override socket path (default: BrokerConfig.socket_path)",
    )
    call_parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        metavar="SEC",
        help="Connect/recv timeout in seconds (default: 10.0)",
    )

    # ── probe-agent subcommand ─────────────────────────────────────────────────
    _default_state_dir = str(Path.home() / ".brontes-probe-mcp")

    pa = subparsers.add_parser(
        "probe-agent",
        help="Manage the host-side pyocd gdbserver daemon",
    )
    pa_sub = pa.add_subparsers(dest="pa_command")

    pa_start = pa_sub.add_parser("start", help="Start probe agent")
    pa_start.add_argument(
        "--target", "-t",
        metavar="TARGET",
        default=None,
        help="pyocd target string (e.g. stm32g474); auto-detected if omitted",
    )
    pa_start.add_argument("--probe-uid", metavar="UID", default=None)
    pa_start.add_argument("--port", type=int, default=None, metavar="PORT")
    pa_start.add_argument("--frequency-hz", type=int, default=None, metavar="HZ")
    pa_start.add_argument("--pack", metavar="PATH", default=None)
    pa_start.add_argument(
        "--state-dir", default=_default_state_dir, metavar="DIR",
        help=(
            "Directory for agent state file (default: ~/.brontes-probe-mcp). "
            "If changed, set PROBE_BROKER_AGENT_STATE_DIR to the same path "
            "so the MCP server can discover the running agent."
        ),
    )

    pa_stop = pa_sub.add_parser("stop", help="Stop probe agent")
    pa_stop.add_argument("--force", action="store_true")
    pa_stop.add_argument("--state-dir", default=_default_state_dir, metavar="DIR")

    pa_status = pa_sub.add_parser("status", help="Show probe agent status")
    pa_status.add_argument("--state-dir", default=_default_state_dir, metavar="DIR")

    # ──────────────────────────────────────────────────────────────────────────

    args = parser.parse_args()

    if args.config_dump:
        config = BrokerConfig()
        print(config.model_dump_json(indent=2))
        return

    if args.command == "serve":
        from brontes_probe_mcp.__main__ import serve_all
        from brontes_probe_mcp.core.broker import BrokerCore

        if args.serve_transports:
            serve_transports: list[str] = [
                t.strip() for t in args.serve_transports.split(",") if t.strip()
            ]
            config = BrokerConfig(transports=serve_transports)
        else:
            config = BrokerConfig()
        broker = BrokerCore(config=config)
        serve_all(config, broker)
        return

    if args.command == "session-unlock":
        from brontes_probe_mcp.core.session import SessionManager

        config = BrokerConfig()
        sm = SessionManager(config)
        lock_path = sm._lock_path()
        if lock_path.exists():
            lock_path.unlink()
            print(f"Removed stale lock: {lock_path}")
        else:
            print(f"No lock file at {lock_path}")
        return

    if args.command == "call":
        _cmd_call(args)
        return

    if args.command == "probe-agent":
        if args.pa_command == "start":
            _cmd_probe_agent_start(args)
        elif args.pa_command == "stop":
            _cmd_probe_agent_stop(args)
        elif args.pa_command == "status":
            _cmd_probe_agent_status(args)
        else:
            pa.print_help()
        return

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
