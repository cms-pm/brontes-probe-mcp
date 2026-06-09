# SPDX-License-Identifier: Apache-2.0
"""Hardware tests — ITM/SWO stream state management."""
from __future__ import annotations

from typing import Any

import pytest

from tests.shared.assertions import assert_itm_handle_shape

pytestmark = pytest.mark.hardware

# ITM probe firmware parameters
_CPU_CLOCK_HZ = 160_000_000
_TRACE_CLOCK_HZ = 2_000_000
_PORTS = [0]


def test_itm_stream_start(hil_session_with_firmware: Any) -> None:
    result = hil_session_with_firmware.itm_stream_start(
        ports=_PORTS,
        cpu_clock_hz=_CPU_CLOCK_HZ,
        trace_clock_hz=_TRACE_CLOCK_HZ,
    )
    assert_itm_handle_shape(result)
    hil_session_with_firmware.itm_stream_stop()


def test_itm_ports_match_request(hil_session_with_firmware: Any) -> None:
    result = hil_session_with_firmware.itm_stream_start(
        ports=_PORTS,
        cpu_clock_hz=_CPU_CLOCK_HZ,
        trace_clock_hz=_TRACE_CLOCK_HZ,
    )
    assert result.ports == _PORTS
    hil_session_with_firmware.itm_stream_stop()


def test_itm_trace_clock_match_request(hil_session_with_firmware: Any) -> None:
    result = hil_session_with_firmware.itm_stream_start(
        ports=_PORTS,
        cpu_clock_hz=_CPU_CLOCK_HZ,
        trace_clock_hz=_TRACE_CLOCK_HZ,
    )
    assert result.trace_clock_hz == _TRACE_CLOCK_HZ
    hil_session_with_firmware.itm_stream_stop()


def test_itm_stream_stop(hil_session_with_firmware: Any) -> None:
    hil_session_with_firmware.itm_stream_start(
        ports=_PORTS,
        cpu_clock_hz=_CPU_CLOCK_HZ,
        trace_clock_hz=_TRACE_CLOCK_HZ,
    )
    result = hil_session_with_firmware.itm_stream_stop()
    assert result.stopped is True


def test_itm_stream_start_stop_cycle(hil_session_with_firmware: Any) -> None:
    for _ in range(2):
        handle = hil_session_with_firmware.itm_stream_start(
            ports=_PORTS,
            cpu_clock_hz=_CPU_CLOCK_HZ,
            trace_clock_hz=_TRACE_CLOCK_HZ,
        )
        assert_itm_handle_shape(handle)
        summary = hil_session_with_firmware.itm_stream_stop()
        assert summary.stopped is True
