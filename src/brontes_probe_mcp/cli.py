# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from brontes_probe_mcp import __version__
from brontes_probe_mcp.core.config import BrokerConfig


def _agent_discover_target(pyocd_bin: str) -> str | None:
    """Return target string from the sole connected probe, or None if ambiguous."""
    try:
        result = subprocess.run(
            [pyocd_bin, "json", "--probes"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        boards = data.get("boards", [])
        if len(boards) == 1:
            return str(boards[0]["target"]) if boards[0].get("target") else None
        return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, OSError):
        return None


def _cmd_probe_agent_start(args: argparse.Namespace) -> None:
    from brontes_probe_mcp.core.session import SessionManager

    config = BrokerConfig(log_dir=args.state_dir)
    mgr = SessionManager(config=config)

    target = args.target
    if not target:
        target = _agent_discover_target(config.pyocd_bin)
        if not target:
            probes_result = subprocess.run(
                [config.pyocd_bin, "json", "--probes"],
                capture_output=True, text=True, check=False,
            )
            try:
                count = len(json.loads(probes_result.stdout).get("boards", []))
            except (json.JSONDecodeError, AttributeError):
                count = 0
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
        help="Directory for agent state file (default: ~/.brontes-probe-mcp)",
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
