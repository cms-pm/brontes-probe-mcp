# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.transports.stdio import run


def main() -> None:
    run(BrokerCore())


if __name__ == "__main__":
    main()
