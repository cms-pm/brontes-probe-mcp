# Board Opportunity Register — Broker Core Reliability
# Source: MTG-0001 — 2026-06-04

## Register Entries

| ID | Source Meeting | Severity | Opportunity / Gap | Required Adjustment | Owner | Target Window | Closure Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| COM-001 | MTG-0001 | Critical | `_run_gdb` discards stderr and uses `check=False`; every probe op returns success regardless of actual GDB outcome | Inspect `returncode` + stderr in `_run_gdb`; raise on failure; surface as `broker_internal_error` | Chris Slothouber | Before chunk 1.3 | `tests/test_broker_core.py`: test asserting GDB non-zero exit → error response | Open |
| COM-002 | MTG-0001 | Critical | No session guard on probe operations — `halt`/`resume`/`reset`/`mem_read`/`program` execute without checking session state | Add session-state guard at `_run_gdb` callsites; surface `kind: session_required` error shape | Chris Slothouber | Before chunk 1.3 | `tests/test_broker_core.py`: test asserting `halt()` on no-session broker → error response | Open |
| COM-003 | MTG-0001 | High | `MemReadResult.value` is raw GDB dump text; `format` param ignored; `programmed_bytes` reports file size not flash size | Parse GDB `x/wx` output per `format`; parse `load` output for `programmed_bytes` | Chris Slothouber | Chunk 1.3 window | `test_mem_read_format_hex`, `test_mem_read_format_bytes`, `test_program_bytes` | Open |
| COM-004 | MTG-0001 | High | `LaneSupervisor._lane_states` (plain dict) and `ItmSwoLane` instance vars have no mutex; three concurrent transport threads share one `BrokerCore` | Add `threading.Lock` to `LaneSupervisor` and `ItmSwoLane` | Chris Slothouber | Chunk 1.3 window | Concurrent-mutation test under `threading` | Open |
| COM-005 | MTG-0001 | High | `session_stop()` calls `os.kill(pid, sig)` ignoring recorded `process_group_id`; child processes survive | Replace with `os.killpg(pgid, sig)` reading `process_group_id` from meta | Chris Slothouber | Chunk 1.3 window | `test_session_stop_kills_process_group` verifying `os.killpg` called with recorded PGID | Open |
| COM-006 | MTG-0001 | Medium | `_OperationLock` (`O_CREAT|O_EXCL`) has no stale-lock detection; crash leaves permanent lock | mtime-based stale detection + `session_unlock` CLI subcommand + ops runbook entry | Chris Slothouber | Chunk 1.3 window | Test: crash-then-reacquire after threshold confirms auto-recovery | Open |
| COM-007 | MTG-0001 | Medium | `blackbox_export` calls `pyocd pack export` (non-existent subcommand); failure swallowed; `bytes_written=0` returned | Correct command or structured `not_implemented` error; never return success for zero-byte write | Chris Slothouber | Chunk 1.3 window | Test: pyocd exit-1 on `blackbox_export` → error response, not `bytes_written=0` | Open |
| COM-008 | MTG-0001 | Medium | Launcher: (a) stdio-only config triggers `docker run` unconditionally; (b) stopped-container name collision fails; (c) `tcp_allow_remote` declared but never enforced | (a) skip try-connect for stdio-only; (b) `docker rm -f` before `docker run`; (c) enforce or remove `tcp_allow_remote` | Chris Slothouber | Chunk 1.3 window | Launcher tests: stopped-container scenario; stdio-only scenario; `tcp_allow_remote` enforcement | Open |
| COM-009 | MTG-0001 | Medium | Multi-profile storage in `SessionManager` vs. single-session `BrokerCore` API — semantics unclear; `session_status()` non-deterministic with multiple profiles | Pool question PQ-001 → ADR → impl aligned to spec | Chris Slothouber | Chunk 1.3 window | PQ-001 closed; implementation + test covering clarified single/multi semantics | Open |
| COM-010 | MTG-0001 | Low | `cli.py` top-level `--transports` flag duplicates `serve --transports` with no docs | Remove top-level `--transports` path before 1.4 | Chris Slothouber | Before 1.4 | `tests/test_cli.py`: top-level `--transports` rejected; `serve --transports` passes | Open |

---

## Machine-Readable Register (JSON)

```json
[
  {
    "opportunityId": "COM-001",
    "sourceMeetingId": "MTG-0001",
    "severity": "Critical",
    "gap": "_run_gdb uses check=False and discards stderr; probe operations return success-shaped models regardless of actual GDB outcome.",
    "requiredAdjustment": "Inspect returncode and stderr in _run_gdb; raise on failure; surface as broker_internal_error via dispatch/_call_handler.",
    "owner": "Chris Slothouber",
    "targetWindow": "Before chunk 1.3 start",
    "closureEvidence": "tests/test_broker_core.py: GDB non-zero exit produces error response shape.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-002",
    "sourceMeetingId": "MTG-0001",
    "severity": "Critical",
    "gap": "halt/resume/reset/mem_read/program execute without checking session state. Pre-session calls silently succeed.",
    "requiredAdjustment": "Session-state guard at _run_gdb callsites. kind: session_required error shape defined in models.",
    "owner": "Chris Slothouber",
    "targetWindow": "Before chunk 1.3 start",
    "closureEvidence": "tests/test_broker_core.py: halt() on no-session broker returns error response with kind=session_required.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-003",
    "sourceMeetingId": "MTG-0001",
    "severity": "High",
    "gap": "MemReadResult.value is raw GDB dump text. format parameter (hex/bytes) ignored. programmed_bytes reports ELF file size not flash bytes.",
    "requiredAdjustment": "Parse GDB x/wx output into structured format per format param. Parse GDB load output for programmed_bytes.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_mem_read_format_hex, test_mem_read_format_bytes, test_program_bytes assert correct shapes.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-004",
    "sourceMeetingId": "MTG-0001",
    "severity": "High",
    "gap": "LaneSupervisor._lane_states and ItmSwoLane state fields unprotected. Three concurrent transport threads share one BrokerCore.",
    "requiredAdjustment": "Add threading.Lock to LaneSupervisor and ItmSwoLane.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "Concurrent-mutation test under threading confirms no torn state.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-005",
    "sourceMeetingId": "MTG-0001",
    "severity": "High",
    "gap": "session_stop kills only the parent PID, not the process group. Child processes survive.",
    "requiredAdjustment": "Use os.killpg(pgid, sig) reading process_group_id from session meta.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_session_stop_kills_process_group verifies os.killpg called with recorded PGID.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-006",
    "sourceMeetingId": "MTG-0001",
    "severity": "Medium",
    "gap": "_OperationLock has no stale-lock detection. Crash leaves permanent lock with no recovery path.",
    "requiredAdjustment": "mtime-based stale detection. session_unlock CLI subcommand. Ops runbook entry.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "Test: crash-then-reacquire after mtime threshold confirms auto-recovery.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-007",
    "sourceMeetingId": "MTG-0001",
    "severity": "Medium",
    "gap": "blackbox_export calls 'pyocd pack export' which does not exist. Failure swallowed. Success reported with bytes_written=0.",
    "requiredAdjustment": "Correct command or structured not_implemented error. Never return success for zero-byte write.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "Test: pyocd exit-1 on blackbox_export returns error response.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-008",
    "sourceMeetingId": "MTG-0001",
    "severity": "Medium",
    "gap": "Launcher: stdio-only config triggers unconditional docker run; stopped-container name collision unhandled; tcp_allow_remote config field never read.",
    "requiredAdjustment": "Three launcher fixes: stdio-only guard, docker rm -f on collision, enforce or remove tcp_allow_remote.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "Launcher tests covering all three scenarios.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-009",
    "sourceMeetingId": "MTG-0001",
    "severity": "Medium",
    "gap": "SessionManager multi-profile storage vs. single-session API. session_status() non-deterministic with multiple profiles.",
    "requiredAdjustment": "Pool question PQ-001 → ADR → implementation aligned to protocol spec.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "PQ-001 closed; implementation updated; test covers clarified semantics.",
    "status": "Open"
  },
  {
    "opportunityId": "COM-010",
    "sourceMeetingId": "MTG-0001",
    "severity": "Low",
    "gap": "CLI top-level --transports flag duplicates serve --transports subcommand. No docs. Confuses integrators.",
    "requiredAdjustment": "Remove top-level --transports before 1.4.",
    "owner": "Chris Slothouber",
    "targetWindow": "Before 1.4",
    "closureEvidence": "tests/test_cli.py: top-level --transports rejected; serve --transports passes.",
    "status": "Open"
  }
]
```

---

## Closure Summary

- Closed this cycle: 0
- Deferred this cycle: 0 (all adopted, windows assigned)
- Rejected this cycle: 0
- Open critical blockers: **2** (COM-001, COM-002 — gate chunk 1.3 start)
- Open high blockers: 3 (COM-003, COM-004, COM-005 — gate 1.4)
- Open medium: 4 (COM-006, COM-007, COM-008, COM-009 — gate 1.4)
- Open low: 1 (COM-010 — gate 1.4)
