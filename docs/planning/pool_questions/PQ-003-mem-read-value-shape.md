# PQ-003 — What is the Expected Shape of `MemReadResult.value`?

## Status
Open

## Source
MTG-0001 (FND-003), 2026-06-04

## Question
What is the canonical shape of `MemReadResult.value` for each `format`
value (`"hex"`, `"bytes"`)?

## Context

The current implementation reads memory via GDB `x/<n>wx 0x<addr>` and
returns the raw stdout as `value: str`. Examples of actual GDB output:
```
0x20000000:	0x00000000	0x00000000	0x00000000	0x00000000
```
This is not useful structured data. The `format` parameter (`"hex"` or
`"bytes"`) is present in the MCP input schema but completely ignored —
output is always raw GDB text.

## Options

### A — List of hex strings per word (format="hex")
```json
{"addr": 536870912, "length": 16, "value": ["0x00000000", "0x00000000", "0x00000000", "0x00000000"]}
```
Parseable by clients without understanding GDB output format. Consistent
word-granularity. `format="hex"` default.

### B — Flat hex string (format="hex")
```json
{"addr": 536870912, "length": 16, "value": "00000000000000000000000000000000"}
```
Compact, but loses word boundaries and is harder to read.

### C — Base64-encoded bytes (format="bytes")
```json
{"addr": 536870912, "length": 16, "value": "AAAAAAAAAAAAAAAAAAAAAA=="}
```
Lossless, transport-safe, but requires base64 decode on the client side.

### D — List of integers (format="bytes")
```json
{"addr": 536870912, "length": 16, "value": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}
```
Explicit byte array. Easy to inspect but verbose.

## Recommendation (pending protocol spec confirmation)
Likely: `format="hex"` → Option A (list of hex word strings, e.g.
`["0xDEADBEEF"]`). `format="bytes"` → Option C (base64). This matches
common embedded tool conventions and is unambiguous to parse.

## Decision Needed
Confirm which shape the protocol spec mandates. `MemReadResult.value` type
in `models.py` must change from `str` to the appropriate Python type to
match.

## Resolution Criteria
- Protocol spec (`probe-broker-protocol.md`) defines `mem_read` response
  value shape.
- `MemReadResult.value` typed accordingly.
- `format` parameter honoured in `BrokerCore.mem_read`.
- `test_mem_read_format_hex` and `test_mem_read_format_bytes` assert the
  correct output shapes.

## Raised By
MTG-0001 / COM-003 (reliability review, 2026-06-04)
