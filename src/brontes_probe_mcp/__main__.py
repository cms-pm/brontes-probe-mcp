# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import signal
import threading

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports import socket as socket_transport
from brontes_probe_mcp.transports import stdio as stdio_transport
from brontes_probe_mcp.transports import tcp as tcp_transport
from brontes_probe_mcp.transports.tcp import _resolve_token


def serve_all(config: BrokerConfig, broker: BrokerCore) -> None:
    """Start all enabled transports as daemon threads and wait for them."""
    threads: list[threading.Thread] = []
    if "socket" in config.transports:
        threads.append(
            threading.Thread(
                target=socket_transport.run,
                args=(broker, config),
                daemon=True,
            )
        )
    if "tcp" in config.transports:
        if _resolve_token(config) is None:
            raise RuntimeError(
                "TCP transport requires a bearer token; "
                "set PROBE_BROKER_TOKEN or PROBE_BROKER_TOKEN_FILE"
            )
        threads.append(
            threading.Thread(
                target=tcp_transport.run,
                args=(broker, config),
                daemon=True,
            )
        )
    if "stdio" in config.transports:
        threads.append(
            threading.Thread(
                target=stdio_transport.run,
                args=(broker,),
                daemon=True,
            )
        )
    for t in threads:
        t.start()
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        pass


def main() -> None:
    signal.signal(signal.SIGTERM, lambda *_: None)
    config = BrokerConfig()
    broker = BrokerCore(config=config)
    serve_all(config, broker)


if __name__ == "__main__":
    main()
