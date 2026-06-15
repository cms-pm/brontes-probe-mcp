# SPDX-License-Identifier: Apache-2.0
"""ITM/SWO byte sources and first-pass software-packet decoder.

The decoder is intentionally a best-effort first pass: it extracts SWIT
(software instrumentation trace) packets and counts overflow bytes.
Local/global timestamp, sync, and DWT extension packets are recognised
only enough to keep the parser in sync — their payloads are skipped.

Full CoreSight TPIU / DWT decode is out of scope for chunk 2.1.1.
"""
from __future__ import annotations

import socket
import time
from typing import Protocol


class SwoSource(Protocol):
    """Source of raw SWO bytes for a single capture session.

    read() returns up to max_bytes; b'' on timeout or no data available.
    close() releases backing resources (sockets, file handles).
    """

    def read(self, max_bytes: int = 4096) -> bytes: ...
    def close(self) -> None: ...


class NullSwoSource:
    """No-op source: yields nothing.

    Used as the default when no real SWO transport is wired (e.g. a
    pyocd gdbserver started without --trace-buffer). The capture lane
    still runs, but bytes_captured stays at 0.
    """

    def read(self, max_bytes: int = 4096) -> bytes:
        time.sleep(0.05)
        return b""

    def close(self) -> None:
        return None


class PyocdSwvTcpSource:
    """SWO source backed by pyocd gdbserver's SWV TCP channel.

    pyocd gdbserver exposes raw SWV bytes on a separate TCP port when
    started with --trace-buffer. If the connection fails (port closed,
    refused, --trace-buffer not enabled), the source degrades silently
    to NullSwoSource behaviour so the broker stays operational.
    """

    def __init__(
        self, host: str, port: int, connect_timeout: float = 0.5
    ) -> None:
        self._sock: socket.socket | None = None
        try:
            sock = socket.create_connection((host, port), timeout=connect_timeout)
            sock.settimeout(0.2)
            self._sock = sock
        except OSError:
            self._sock = None

    def read(self, max_bytes: int = 4096) -> bytes:
        sock = self._sock
        if sock is None:
            time.sleep(0.05)
            return b""
        try:
            return sock.recv(max_bytes)
        except TimeoutError:
            return b""
        except OSError:
            return b""

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


# ── ITM decoder ───────────────────────────────────────────────────────────────

# SWIT (software) packet header layout: 0bPPPPP0SS
#   bits 7:3 → stimulus port (0..31)
#   bit 2    → 0 (distinguishes from protocol packets)
#   bits 1:0 → size code: 01→1B, 10→2B, 11→4B (00 reserved)
_SWIT_SIZE_FOR_CODE: dict[int, int] = {0b01: 1, 0b10: 2, 0b11: 4}

_OVERFLOW_BYTE = 0x70


def is_swit_header(b: int) -> bool:
    return (b & 0b100) == 0 and (b & 0b11) != 0


def decode_software_packets(
    buf: bytes,
    port_filter: set[int] | None = None,
) -> tuple[list[dict[str, object]], int]:
    """Return (records, packet_count) extracted from buf.

    Each record: {"port": int, "timestamp_us": int|null, "data_hex": str}.
    timestamp_us is null in this first-pass decoder (timestamp packets are
    consumed to keep alignment but not correlated to SWIT events).

    port_filter, if given, restricts the emitted records to those ports.
    Packets on excluded ports are still consumed (and count toward the
    second return value) so the parser advances correctly.
    """
    records: list[dict[str, object]] = []
    i = 0
    n = len(buf)
    packet_count = 0
    while i < n:
        b = buf[i]

        if b == _OVERFLOW_BYTE:
            i += 1
            continue

        if b == 0x00:
            # Sync packet padding.
            i += 1
            continue

        if is_swit_header(b):
            size_code = b & 0b11
            size = _SWIT_SIZE_FOR_CODE[size_code]
            port = (b >> 3) & 0x1F
            if i + 1 + size > n:
                break
            data = buf[i + 1 : i + 1 + size]
            packet_count += 1
            if port_filter is None or port in port_filter:
                records.append(
                    {
                        "port": port,
                        "timestamp_us": None,
                        "data_hex": data.hex(),
                    }
                )
            i += 1 + size
            continue

        # Protocol packet: consume header + continuation bytes (high bit set).
        i += 1
        while i < n and (buf[i] & 0x80):
            i += 1
        if i < n:
            i += 1

    return records, packet_count


def count_overflow_bytes(buf: bytes) -> int:
    return buf.count(_OVERFLOW_BYTE)
