# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import signal
import threading

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports import socket as socket_transport
from brontes_probe_mcp.transports import stdio as stdio_transport
from brontes_probe_mcp.transports import tcp as tcp_transport


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
    config = BrokerConfig()
    broker = BrokerCore(config=config)
    serve_all(config, broker)


# Allow SIGTERM to cleanly exit
signal.signal(signal.SIGTERM, lambda *_: None)

if __name__ == "__main__":
    main()
