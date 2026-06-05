# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import sys

from brontes_probe_mcp import __version__
from brontes_probe_mcp.core.config import BrokerConfig


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

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
