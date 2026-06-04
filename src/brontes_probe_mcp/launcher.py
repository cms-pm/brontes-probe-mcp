# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import fcntl
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

from brontes_probe_mcp.core.config import BrokerConfig


def _lock_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(runtime) / "brontes-probe-mcp.lock"


def _try_connect_socket(sock_path: str) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(sock_path)
        return True
    except OSError:
        return False


def _try_connect_tcp(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            pass
        return True
    except OSError:
        return False


def launch(
    config: BrokerConfig,
    docker_image: str = "ghcr.io/cms-pm/brontes-probe-mcp",
    extra_docker_args: list[str] | None = None,
) -> None:
    """Ensure the broker is running; start via Docker if not already up."""
    lock_path = _lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            # Check if already up
            if "socket" in config.transports:
                if _try_connect_socket(config.socket_path):
                    print(f"Already running at {config.socket_path}")
                    return
            if "tcp" in config.transports:
                if _try_connect_tcp(config.tcp_host, config.tcp_port):
                    print(f"Already running at {config.tcp_host}:{config.tcp_port}")
                    return

            # Not running — start via Docker
            docker_args: list[str] = [
                "docker",
                "run",
                "-d",
                "--name",
                "brontes-probe-mcp",
            ]
            if extra_docker_args:
                docker_args.extend(extra_docker_args)
            docker_args.append(docker_image)

            result: Any = subprocess.run(
                docker_args, capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"docker run failed: {result.stderr.strip()}"
                )
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
