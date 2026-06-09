# SPDX-License-Identifier: Apache-2.0
"""Hardware tests for probe_discover and target_suggest.

These do not require an active session — they run pyocd json --probes / --targets
directly. A probe must be physically connected for probe_discover to return results;
target_suggest works with or without a connected probe (queries installed packs).

Run with:  pytest -m hardware tests/hardware/test_hardware_discovery.py
"""
from __future__ import annotations

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.models import ProbeDiscoverResult, TargetSuggestResult

pytestmark = pytest.mark.hardware


# ── probe_discover ────────────────────────────────────────────────────────────

def test_probe_discover_returns_result(hil_broker: BrokerCore) -> None:
    result = hil_broker.probe_discover()
    assert isinstance(result, ProbeDiscoverResult)


def test_probe_discover_finds_connected_probe(hil_broker: BrokerCore) -> None:
    result = hil_broker.probe_discover()
    assert len(result.probes) >= 1, "Expected at least one probe connected"


def test_probe_discover_probe_has_uid(hil_broker: BrokerCore) -> None:
    result = hil_broker.probe_discover()
    for probe in result.probes:
        assert probe.uid, "Each probe must have a non-empty uid"


def test_probe_discover_probe_has_description(hil_broker: BrokerCore) -> None:
    result = hil_broker.probe_discover()
    for probe in result.probes:
        assert probe.description or probe.product_name, (
            "Probe must have description or product_name"
        )


def test_probe_discover_no_session_required(hil_broker: BrokerCore) -> None:
    # hil_broker has no active session — must succeed anyway
    assert hil_broker._session_state != "healthy"
    result = hil_broker.probe_discover()
    assert isinstance(result, ProbeDiscoverResult)


# ── target_suggest ────────────────────────────────────────────────────────────

def test_target_suggest_returns_result(hil_broker: BrokerCore) -> None:
    result = hil_broker.target_suggest("stm32g4")
    assert isinstance(result, TargetSuggestResult)


def test_target_suggest_query_echoed(hil_broker: BrokerCore) -> None:
    result = hil_broker.target_suggest("stm32g4")
    assert result.query == "stm32g4"


def test_target_suggest_no_session_required(hil_broker: BrokerCore) -> None:
    assert hil_broker._session_state != "healthy"
    result = hil_broker.target_suggest("cortex")
    assert isinstance(result, TargetSuggestResult)


def test_target_suggest_with_pack(
    hil_broker: BrokerCore, hil_pack: str
) -> None:
    result = hil_broker.target_suggest("stm32g474", pack=hil_pack)
    assert isinstance(result, TargetSuggestResult)
    assert result.pack == hil_pack
    assert len(result.targets) > 0, "Pack must contain stm32g474 targets"


def test_target_suggest_pack_targets_have_name(
    hil_broker: BrokerCore, hil_pack: str
) -> None:
    result = hil_broker.target_suggest("stm32g474", pack=hil_pack)
    for target in result.targets:
        assert target.name, "Each target must have a non-empty name"
        assert target.vendor, "Each target must have a vendor"


def test_target_suggest_contains_exact_target(
    hil_broker: BrokerCore, hil_pack: str, hil_target: str
) -> None:
    result = hil_broker.target_suggest(hil_target, pack=hil_pack)
    names = [t.name for t in result.targets]
    assert any(hil_target in n for n in names), (
        f"{hil_target!r} must match at least one target name; got {names[:5]}"
    )


def test_target_suggest_empty_for_garbage(hil_broker: BrokerCore) -> None:
    result = hil_broker.target_suggest("zzz_no_such_mcu_zzz")
    assert result.targets == []


def test_target_suggest_source_field(
    hil_broker: BrokerCore, hil_pack: str
) -> None:
    result = hil_broker.target_suggest("stm32g474", pack=hil_pack)
    for target in result.targets:
        assert target.source in {"builtin", "pack", "cbuild-run"}
