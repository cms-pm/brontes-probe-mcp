# SPDX-License-Identifier: Apache-2.0
"""Hardware integration tests — require a physical SWD target.

Run with:  pytest -m hardware tests/hardware/
Excluded from CI by default (pytest -m "not hardware").
"""
from __future__ import annotations

from typing import Any

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from tests.shared.assertions import assert_session_status_shape

pytestmark = pytest.mark.hardware


def test_hardware_halt_resume(hil_session: Any) -> None:
    halted = hil_session.halt()
    assert halted.halted is True
    resumed = hil_session.resume()
    assert resumed.resumed is True


def test_hardware_mem_read(hil_session: Any, hil_sram_addr: int) -> None:
    hil_session.halt()
    result = hil_session.mem_read(addr=hil_sram_addr, length=16)
    assert result.addr == hil_sram_addr
    assert result.length == 16


def test_session_status_all_fields(hil_session: Any) -> None:
    result = hil_session.session_status()
    assert_session_status_shape(result)
    assert result.state == "healthy"
    assert result.target is not None


def test_session_status_before_start(hil_isolated_broker: BrokerCore) -> None:
    """Fresh isolated broker with no prior session → state must be stopped."""
    result = hil_isolated_broker.session_status()
    assert_session_status_shape(result)
    assert result.state == "stopped"
