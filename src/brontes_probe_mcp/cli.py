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
    parser.add_argument(
        "--transports",
        metavar="CSV",
        help="Comma-separated transports to start (e.g. stdio,socket,tcp)",
    )

    args = parser.parse_args()

    if args.config_dump:
        config = BrokerConfig()
        print(config.model_dump_json(indent=2))
        return

    if args.transports:
        transports = [t.strip() for t in args.transports.split(",") if t.strip()]
        print(f"Requested transports: {transports}")
        raise NotImplementedError("transport start requires 8.7.2c implementation")

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
