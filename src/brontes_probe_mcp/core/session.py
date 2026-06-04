# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import SessionStatus


class SessionManager:
    def __init__(self, config: BrokerConfig) -> None:
        self._config = config

    def start(self, **profile_kwargs: object) -> SessionStatus:
        raise NotImplementedError("8.7.2a implementation")

    def stop(self, force: bool = False) -> SessionStatus:
        raise NotImplementedError("8.7.2a implementation")

    def status(self) -> SessionStatus:
        raise NotImplementedError("8.7.2a implementation")
