# SPDX-License-Identifier: Apache-2.0
"""Hardware integration tests — require a physical SWD target.

Run with:  pytest -m hardware tests/hardware/
Excluded from CI by default (pytest -m "not hardware").
"""
from __future__ import annotations

import pytest

from brontes_probe_mcp.core.broker import BrokerCore


@pytest.mark.hardware
def test_hardware_session_start_stop() -> None:
    broker = BrokerCore()
    status = broker.session_start(target="stm32g474")
    assert status.state == "healthy"
    stopped = broker.session_stop()
    assert stopped.state == "stopped"


@pytest.mark.hardware
def test_hardware_halt_resume() -> None:
    broker = BrokerCore()
    broker.session_start(target="stm32g474")
    halted = broker.halt()
    assert halted.halted is True
    resumed = broker.resume()
    assert resumed.resumed is True
    broker.session_stop()


@pytest.mark.hardware
def test_hardware_mem_read() -> None:
    broker = BrokerCore()
    broker.session_start(target="stm32g474")
    broker.halt()
    result = broker.mem_read(addr=0x20000000, length=16)
    assert result.addr == 0x20000000
    assert result.length == 16
    broker.session_stop()
