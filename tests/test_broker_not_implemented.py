# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from brontes_probe_mcp.core.broker import BrokerCore


@pytest.fixture()
def broker() -> BrokerCore:
    return BrokerCore()


def test_program_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.program(artifact=Path("/dev/null"))


def test_halt_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.halt()


def test_resume_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.resume()


def test_reset_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.reset()


def test_mem_read_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.mem_read(addr=0x20000000, length=4)


def test_blackbox_export_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.blackbox_export(out=Path("/tmp/test.tar"))


def test_itm_stream_start_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.itm_stream_start(ports=[0, 1])


def test_itm_stream_stop_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.itm_stream_stop()


def test_lane_status_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.lane_status()


def test_lane_release_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.lane_release(lane="swd")


def test_lane_resume_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.lane_resume(lane="swd")


def test_recent_lines_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.recent_lines()


def test_session_start_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.session_start(target="stm32g474", probe_uid="abc123")


def test_session_stop_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.session_stop()


def test_session_status_raises(broker: BrokerCore) -> None:
    with pytest.raises(NotImplementedError, match="8.7.2b"):
        broker.session_status()
