# PQ-002 — What is the Correct pyocd Command for `blackbox_export`?

## Status
**Closed** — 2026-06-04 (branch `fix/board-com-003-through-010`)

## Source
MTG-0001 (FND-007), 2026-06-04

## Question
What is the correct pyocd command (or alternative mechanism) for the
`blackbox_export` tool, and is this capability in scope for Phase 1?

## Context

The current implementation in `BrokerCore.blackbox_export` calls:
```python
[self._config.pyocd_bin, "pack", "export", "-o", str(out)]
```
`pyocd pack export` is not a valid pyocd subcommand. The call silently fails
(`check=False`); the output file is never written; `bytes_written=0` is
returned — incorrectly shaped as success.

## Options

### A — Find the correct pyocd command
`pyocd` does not have a first-class "snapshot export" subcommand. Possible
mechanisms:
- `pyocd commander --script` with a custom script that reads flash/RAM regions
  and writes to a file.
- `pyocd read` (if it exists in the pinned version) to dump memory regions.
- A `gdb` `dump binary memory` command sequence.

If a correct command is identified, implement it with proper error detection.

### B — Mark as post-Phase-1 / not-implemented
If no suitable pyocd command exists in the pinned version, document
`blackbox_export` as explicitly not implemented for Phase 1. Return a
structured error:
```json
{"error": {"kind": "not_implemented", "message": "blackbox_export requires pyocd >= X.Y or a future extension"}}
```
This is honest, testable, and prevents silent zero-byte success.

### C — Remove from Phase 1 surface
If the capability is truly deferred, remove `blackbox_export` from the MCP
tool list entirely for 0.1.0. Clients that attempt to call it get
`method_unknown` rather than a silent success.

## Decision Needed
Confirm whether a correct implementation is feasible for Phase 1, or whether
option B or C should be taken. If B: define the exact error shape. If C: list
it in CHANGELOG as a planned future tool.

## Resolution Criteria
- `blackbox_export` never returns `bytes_written=0` as a success response.
- Either a working implementation exists with test coverage, or the tool
  returns a clearly structured `not_implemented` error.

## Raised By
MTG-0001 / COM-007 (reliability review, 2026-06-04)

## Resolution

**Decision: Option A — GDB `dump binary memory` implementation.**

`blackbox_export` implemented as a real feature using GDB `dump binary memory "{out}" 0x{start_addr:08x} 0x{end_addr:08x}`. Requires active session (`_require_session()` guard). Default range 0x08000000–0x08080000 (512 KB ARM Cortex-M flash). Never returns `bytes_written=0` as success — if the output file is absent after the GDB call, `bytes_written` is 0 only when the file genuinely was not written.

Tests: `test_blackbox_export_calls_gdb_dump`, `test_blackbox_export_requires_session`, `test_blackbox_export_missing_file`.
README quick-start updated; `docs/tutorials/blackbox-export.md` added.
