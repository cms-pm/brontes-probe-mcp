# SPDX-License-Identifier: Apache-2.0
"""Typed broker errors exposed across the public RPC surface.

Each error carries enough structured detail for callers (humans or LLMs)
to recover without grepping a free-form stderr string.
"""
from __future__ import annotations


class BrokerError(RuntimeError):
    """Base class for typed broker errors."""


class PackIndexCorruptError(BrokerError):
    """Raised when pyOCD's pack index is unreadable (e.g. truncated JSON).

    The retrospective failure mode: ``json.decoder.JSONDecodeError: Extra
    data: line 1272628 column 7`` surfaces from any pack-touching call.
    Callers should run ``pack_cache_reset`` to recover.
    """

    def __init__(
        self,
        message: str,
        *,
        cause_class: str,
        cause_message: str,
        index_path_hint: str,
        remediation: str = "brontes-probe-mcp-cli call pack_cache_reset",
    ) -> None:
        super().__init__(message)
        self.cause_class = cause_class
        self.cause_message = cause_message
        self.index_path_hint = index_path_hint
        self.remediation = remediation


class PackParseError(BrokerError):
    """Raised when a local PDSC file cannot be parsed."""

    def __init__(self, message: str, *, pdsc_path: str) -> None:
        super().__init__(message)
        self.pdsc_path = pdsc_path
