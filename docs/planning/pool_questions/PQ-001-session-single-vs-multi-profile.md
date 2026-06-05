# PQ-001 — Session: Single-Target or Multi-Target Semantics?

## Status
Open

## Source
MTG-0001 (FND-009), 2026-06-04

## Question
Does the `brontes-probe-mcp` protocol spec intend single-session (one target at a
time) or multi-session (concurrent targets, each with an independent GDB server)
semantics?

## Context

`SessionManager` currently writes one `.json` profile per target under `log_dir/`:
```
<log_dir>/<target-name>.json
```
`_active_profiles()` lists all such files, implying concurrent sessions are
possible. However:

- `BrokerCore` holds one set of toolchain settings (`gdb_port`, `gdb_host`,
  `gdb_bin`, `pyocd_bin`) — all single-valued.
- `session_status()` returns only `list(_active_profiles())[0]` — the first
  found, non-deterministically.
- `session_stop()` kills **all** active profiles.
- The MCP tool schema for `session_start` accepts a single `target` and
  `probe_uid`.

This is a contract ambiguity: the storage layer is multi-profile, but the
query and toolchain layers are single-session.

## Options

### A — Single-session (one active target at a time)
Simplify `SessionManager` to one fixed profile path (`default.json`). Calling
`session_start` while a session is active either fails or implicitly stops the
prior one (define clearly). This matches the current `BrokerCore` toolchain
constraints.

**Pros:** Simple. Matches real hardware (one probe, one target per physical
connection in most embedded setups). Easier to reason about.  
**Cons:** Multi-probe use cases (e.g. flashing two devices in parallel) require
separate broker instances or a future extension.

### B — Multi-session (concurrent targets)
Keep multi-profile storage. Fix `session_status(target: str)` to look up a
specific profile. `BrokerConfig` grows per-target overrides (separate
`gdb_port` per target). `session_stop(target: str)` stops one, not all.

**Pros:** Enables multi-probe workflows within one broker process.  
**Cons:** Significant implementation scope. `BrokerCore` toolchain settings
must become per-session. Protocol spec needs corresponding extension.

## Decision Needed
Confirm which option is canonical. Update `SessionManager`, `BrokerCore`,
and the `session_start`/`session_status`/`session_stop` MCP schemas accordingly.

## Resolution Criteria
- Protocol spec (`probe-broker-protocol.md`) confirms the intended semantics.
- Implementation aligns.
- `test_session_manager.py` covers the clarified single/multi case.

## Raised By
MTG-0001 / COM-009 (reliability review, 2026-06-04)
