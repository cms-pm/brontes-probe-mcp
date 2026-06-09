# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from brontes_probe_mcp.core.config import BrokerConfig


def test_default_transports() -> None:
    config = BrokerConfig()
    assert config.transports == ["stdio", "socket"]


def test_default_socket_path() -> None:
    from pathlib import Path
    config = BrokerConfig()
    assert config.socket_path == str(Path.home() / ".brontes-probe-mcp" / "probe.sock")


def test_default_tcp_host() -> None:
    config = BrokerConfig()
    assert config.tcp_host == "127.0.0.1"


def test_default_tcp_port() -> None:
    config = BrokerConfig()
    assert config.tcp_port == 7172


def test_default_lanes() -> None:
    config = BrokerConfig()
    assert config.lanes == ["swd", "itm_swo"]


def test_default_backend() -> None:
    config = BrokerConfig()
    assert config.backend == "pyocd"


def test_default_gdb_port() -> None:
    config = BrokerConfig()
    assert config.gdb_port == 3333


def test_default_digest_check() -> None:
    config = BrokerConfig()
    assert config.digest_check == "enforce"


def test_transports_csv_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBE_BROKER_TRANSPORTS", "stdio,tcp")
    config = BrokerConfig()
    assert config.transports == ["stdio", "tcp"]


def test_transports_single(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBE_BROKER_TRANSPORTS", "stdio")
    config = BrokerConfig()
    assert config.transports == ["stdio"]


def test_transports_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBE_BROKER_TRANSPORTS", "stdio,socket,tcp")
    config = BrokerConfig()
    assert config.transports == ["stdio", "socket", "tcp"]


def test_lanes_csv_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBE_BROKER_LANES", "swd")
    config = BrokerConfig()
    assert config.lanes == ["swd"]


def test_tcp_port_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBE_BROKER_TCP_PORT", "8080")
    config = BrokerConfig()
    assert config.tcp_port == 8080


def test_image_digest_defaults_none() -> None:
    config = BrokerConfig()
    assert config.image_digest is None


def test_image_tag_defaults_none() -> None:
    config = BrokerConfig()
    assert config.image_tag is None
