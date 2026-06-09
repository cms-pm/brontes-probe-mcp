# SPDX-License-Identifier: Apache-2.0
"""Hardware tests — lane supervision (lane ops work without an active session)."""
from __future__ import annotations

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from tests.shared.assertions import assert_lane_status_shape

pytestmark = pytest.mark.hardware


def test_lane_status_initial(hil_broker: BrokerCore) -> None:
    result = hil_broker.lane_status()
    assert isinstance(result, dict)
    assert "swd" in result
    assert "itm_swo" in result
    for lane, status in result.items():
        assert_lane_status_shape(status, lane)


def test_lane_release_swd(hil_broker: BrokerCore) -> None:
    result = hil_broker.lane_release("swd")
    assert_lane_status_shape(result, "swd")
    assert result.released is True


def test_lane_resume_swd(hil_broker: BrokerCore) -> None:
    hil_broker.lane_release("swd")
    result = hil_broker.lane_resume("swd")
    assert_lane_status_shape(result, "swd")
    assert result.resumed is True


def test_lane_release_itm_swo(hil_broker: BrokerCore) -> None:
    result = hil_broker.lane_release("itm_swo")
    assert_lane_status_shape(result, "itm_swo")
    assert result.released is True


def test_lane_resume_itm_swo(hil_broker: BrokerCore) -> None:
    hil_broker.lane_release("itm_swo")
    result = hil_broker.lane_resume("itm_swo")
    assert_lane_status_shape(result, "itm_swo")
    assert result.resumed is True


def test_lane_status_reflects_release(hil_broker: BrokerCore) -> None:
    hil_broker.lane_resume("swd")  # ensure known state
    hil_broker.lane_release("swd")
    status_map = hil_broker.lane_status()
    assert status_map["swd"].released is True


def test_lane_status_reflects_resume(hil_broker: BrokerCore) -> None:
    hil_broker.lane_release("swd")
    hil_broker.lane_resume("swd")
    status_map = hil_broker.lane_status()
    assert status_map["swd"].resumed is True


def test_lane_unknown_raises(hil_broker: BrokerCore) -> None:
    with pytest.raises(ValueError, match="unknown lane"):
        hil_broker.lane_release("bogus_lane")
