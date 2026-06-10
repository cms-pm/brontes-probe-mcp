# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from importlib.metadata import version


def test_package_version() -> None:
    import brontes_probe_mcp

    assert brontes_probe_mcp.__version__ == "0.2.0"
    assert brontes_probe_mcp.__protocol_version__ == "0.1.0"


def test_version_matches_metadata() -> None:
    import brontes_probe_mcp

    pkg_version = version("brontes-probe-mcp")
    assert pkg_version == brontes_probe_mcp.__version__


def test_import_core_config() -> None:
    from brontes_probe_mcp.core.config import BrokerConfig

    assert BrokerConfig is not None


def test_import_core_broker() -> None:
    from brontes_probe_mcp.core.broker import BrokerCore

    assert BrokerCore is not None


def test_import_core_session() -> None:
    from brontes_probe_mcp.core.session import SessionManager

    assert SessionManager is not None


def test_import_core_lanes() -> None:
    from brontes_probe_mcp.core.lanes import ItmSwoLane, LaneSupervisor

    assert LaneSupervisor is not None
    assert ItmSwoLane is not None


def test_import_transports() -> None:
    from brontes_probe_mcp.transports import socket, stdio, tcp

    assert stdio is not None
    assert socket is not None
    assert tcp is not None
