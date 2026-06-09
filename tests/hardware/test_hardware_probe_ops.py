# SPDX-License-Identifier: Apache-2.0
"""Hardware tests — probe operations (halt/resume/reset/mem_read/program/export)."""
from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any

import pytest

from tests.shared.assertions import (
    assert_blackbox_export_shape,
    assert_mem_read_shape,
    assert_probe_state_shape,
    assert_program_result_shape,
)

pytestmark = pytest.mark.hardware


def test_halt(hil_session: Any) -> None:
    result = hil_session.halt()
    assert_probe_state_shape(result)
    assert result.halted is True
    assert result.pc is not None and result.pc > 0


def test_resume(hil_session: Any) -> None:
    hil_session.halt()
    result = hil_session.resume()
    assert_probe_state_shape(result)
    assert result.resumed is True
    assert result.halted is False


def test_halt_resume_cycle(hil_session: Any) -> None:
    for _ in range(3):
        halted = hil_session.halt()
        assert halted.halted is True
        resumed = hil_session.resume()
        assert resumed.resumed is True


def test_reset_soft(hil_session: Any) -> None:
    result = hil_session.reset(kind="soft")
    assert_probe_state_shape(result)
    assert result.reset is True


def test_reset_hard(hil_session: Any) -> None:
    result = hil_session.reset(kind="hard")
    assert_probe_state_shape(result)
    assert result.reset is True


def test_reset_halt_after(hil_session: Any) -> None:
    result = hil_session.reset(halt_after=True)
    assert_probe_state_shape(result)
    assert result.halted_after is True


def test_mem_read_hex_16(hil_session: Any, hil_sram_addr: int) -> None:
    hil_session.halt()
    result = hil_session.mem_read(addr=hil_sram_addr, length=16, format="hex")
    assert_mem_read_shape(result, hil_sram_addr, 16, "hex")
    assert len(result.value) == 4  # 4 words × 4 bytes = 16 bytes


def test_mem_read_bytes_4(hil_session: Any, hil_sram_addr: int) -> None:
    hil_session.halt()
    result = hil_session.mem_read(addr=hil_sram_addr, length=4, format="bytes")
    assert_mem_read_shape(result, hil_sram_addr, 4, "bytes")
    decoded = base64.b64decode(result.value)
    assert len(decoded) == 4


@pytest.mark.parametrize("length", [1, 4, 16, 64, 256])
def test_mem_read_lengths(hil_session: Any, hil_sram_addr: int, length: int) -> None:
    hil_session.halt()
    result = hil_session.mem_read(addr=hil_sram_addr, length=length)
    assert result.addr == hil_sram_addr
    assert result.length == length


def test_mem_read_deterministic(hil_session: Any, hil_sram_addr: int) -> None:
    hil_session.halt()
    r1 = hil_session.mem_read(addr=hil_sram_addr, length=4, format="hex")
    r2 = hil_session.mem_read(addr=hil_sram_addr, length=4, format="hex")
    assert r1.value == r2.value


def test_probe_program(
    hil_session: Any, hil_elf: Path
) -> None:
    result = hil_session.program(artifact=hil_elf, halt_after=True)
    assert_program_result_shape(result)
    assert result.format == "elf"
    assert result.halted is True


def test_probe_program_no_halt(
    hil_session: Any, hil_elf: Path
) -> None:
    result = hil_session.program(artifact=hil_elf, halt_after=False)
    assert result.programmed_bytes > 0
    assert result.halted is False


def test_blackbox_export(hil_session: Any) -> None:
    hil_session.halt()
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "snap.bin"
        # Export 4 KB of flash (fast; always readable)
        result = hil_session.blackbox_export(
            out=out, start_addr=0x08000000, end_addr=0x08001000
        )
        assert_blackbox_export_shape(result, out)
        assert result.bytes_written == 0x1000  # 4096 bytes
