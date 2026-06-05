# Board Opportunity Register — Broker Core Reliability
# Source: MTG-0001 — 2026-06-04

## Register Entries

| ID | Source Meeting | Severity | Opportunity / Gap | Required Adjustment | Owner | Target Window | Closure Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| COM-001 | MTG-0001 | Critical | `_run_gdb` discards stderr and uses `check=False`; every probe op returns success regardless of actual GDB outcome | Inspect `returncode` + stderr in `_run_gdb`; raise on failure; surface as `broker_internal_error` | Chris Slothouber | Before chunk 1.3 | `tests/test_broker_core.py`: `test_gdb_failure_raises`, `test_gdb_failure_stderr_in_message` | **Closed** (PR #4) |
| COM-002 | MTG-0001 | Critical | No session guard on probe operations — `halt`/`resume`/`reset`/`mem_read`/`program` execute without checking session state | Add session-state guard at `_run_gdb` callsites; surface `kind: session_required` error shape | Chris Slothouber | Before chunk 1.3 | `tests/test_broker_core.py`: `test_probe_op_without_session_raises`, `test_all_probe_ops_require_session`; `tests/test_transport_stdio.py`: `test_probe_op_without_session_returns_session_required` | **Closed** (PR #4) |
| COM-003 | MTG-0001 | High | `MemReadResult.value` is raw GDB dump text; `format` param ignored; `programmed_bytes` reports file size not flash size | Parse GDB `x/wx` output per `format`; parse `load` output for `programmed_bytes` | Chris Slothouber | Chunk 1.3 window | `test_mem_read_format_hex`, `test_mem_read_format_bytes_default`, `test_program_bytes_from_gdb_load_output` | **Closed** (branch `fix/board-com-003-through-010`) |
| COM-004 | MTG-0001 | High | `LaneSupervisor._lane_states` (plain dict) and `ItmSwoLane` instance vars have no mutex; three concurrent transport threads share one `BrokerCore` | Add `threading.Lock` to `LaneSupervisor` and `ItmSwoLane` | Chris Slothouber | Chunk 1.3 window | `test_lane_supervisor_concurrent_mutations` passes (3-thread, 150 ops) | **Closed** (branch `fix/board-com-003-through-010`) |
| COM-005 | MTG-0001 | High | `session_stop()` calls `os.kill(pid, sig)` ignoring recorded `process_group_id`; child processes survive | Replace with `os.killpg(pgid, sig)` reading `process_group_id` from meta | Chris Slothouber | Chunk 1.3 window | `test_session_stop_kills_process_group`, `test_stop_uses_killpg` | **Closed** (branch `fix/board-com-003-through-010`) |
| COM-006 | MTG-0001 | Medium | `_OperationLock` (`O_CREAT|O_EXCL`) has no stale-lock detection; crash leaves permanent lock | mtime-based stale detection + `session_unlock` CLI subcommand + ops runbook entry | Chris Slothouber | Chunk 1.3 window | `test_stale_lock_auto_recovered`, `test_session_unlock_removes_lock`, `test_session_unlock_no_lock` | **Closed** (branch `fix/board-com-003-through-010`) |
| COM-007 | MTG-0001 | Medium | `blackbox_export` calls `pyocd pack export` (non-existent subcommand); failure swallowed; `bytes_written=0` returned | GDB `dump binary memory` implementation; requires active session | Chris Slothouber | Chunk 1.3 window | `test_blackbox_export_calls_gdb_dump`, `test_blackbox_export_requires_session` | **Closed** (branch `fix/board-com-003-through-010`) |
| COM-008 | MTG-0001 | Medium | Launcher: (a) stdio-only config triggers `docker run` unconditionally; (b) stopped-container name collision fails; (c) `tcp_allow_remote` declared but never enforced | (b) removed `--name` from client templates (COM-008b); (c) enforce `tcp_allow_remote` in `serve_all` (COM-008c); (a) deferred — no docker launch code in Python yet | Chris Slothouber | Chunk 1.3 window | `test_tcp_allow_remote_false_rejects_non_loopback`, `test_tcp_allow_remote_true_permits_non_loopback`; client templates updated | **Closed** (COM-008b+c; COM-008a deferred to launcher implementation) |
| COM-009 | MTG-0001 | Medium | Multi-profile storage in `SessionManager` vs. single-session `BrokerCore` API — semantics unclear; `session_status()` non-deterministic with multiple profiles | PQ-001 → Option A: single-session (`default.json`); implicit replace on `session_start` | Chris Slothouber | Chunk 1.3 window | `test_session_status_uses_default_profile`, `test_session_start_replaces_active_session` | **Closed** (branch `fix/board-com-003-through-010`) |
| COM-010 | MTG-0001 | Low | `cli.py` top-level `--transports` flag duplicates `serve --transports` with no docs | Remove top-level `--transports` path before 1.4 | Chris Slothouber | Before 1.4 | `test_top_level_transports_flag_rejected`, `test_serve_transports_flag_accepted` | **Closed** (branch `fix/board-com-003-through-010`) |

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
    "status": "Closed",
    "closedPR": "PR #4",
    "closedDate": "2026-06-04"
  },
  {
    "opportunityId": "COM-003",
    "sourceMeetingId": "MTG-0001",
    "severity": "High",
    "gap": "MemReadResult.value is raw GDB dump text. format parameter (hex/bytes) ignored. programmed_bytes reports ELF file size not flash bytes.",
    "requiredAdjustment": "Parse GDB x/wx output into structured format per format param. Parse GDB load output for programmed_bytes.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_mem_read_format_hex, test_mem_read_format_bytes_default, test_program_bytes_from_gdb_load_output.",
    "status": "Closed",
    "closedBranch": "fix/board-com-003-through-010",
    "closedDate": "2026-06-04"
  },
  {
    "opportunityId": "COM-004",
    "sourceMeetingId": "MTG-0001",
    "severity": "High",
    "gap": "LaneSupervisor._lane_states and ItmSwoLane state fields unprotected. Three concurrent transport threads share one BrokerCore.",
    "requiredAdjustment": "Add threading.Lock to LaneSupervisor and ItmSwoLane.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_lane_supervisor_concurrent_mutations: 3 threads, 150 ops, no torn state.",
    "status": "Closed",
    "closedBranch": "fix/board-com-003-through-010",
    "closedDate": "2026-06-04"
  },
  {
    "opportunityId": "COM-005",
    "sourceMeetingId": "MTG-0001",
    "severity": "High",
    "gap": "session_stop kills only the parent PID, not the process group. Child processes survive.",
    "requiredAdjustment": "Use os.killpg(pgid, sig) reading process_group_id from session meta.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_session_stop_kills_process_group verifies os.killpg called with recorded PGID; test_stop_uses_killpg.",
    "status": "Closed",
    "closedBranch": "fix/board-com-003-through-010",
    "closedDate": "2026-06-04"
  },
  {
    "opportunityId": "COM-006",
    "sourceMeetingId": "MTG-0001",
    "severity": "Medium",
    "gap": "_OperationLock has no stale-lock detection. Crash leaves permanent lock with no recovery path.",
    "requiredAdjustment": "mtime-based stale detection. session_unlock CLI subcommand. Ops runbook entry.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_stale_lock_auto_recovered, test_session_unlock_removes_lock, test_session_unlock_no_lock.",
    "status": "Closed",
    "closedBranch": "fix/board-com-003-through-010",
    "closedDate": "2026-06-04"
  },
  {
    "opportunityId": "COM-007",
    "sourceMeetingId": "MTG-0001",
    "severity": "Medium",
    "gap": "blackbox_export calls 'pyocd pack export' which does not exist. Failure swallowed. Success reported with bytes_written=0.",
    "requiredAdjustment": "GDB dump binary memory implementation; requires active session.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_blackbox_export_calls_gdb_dump, test_blackbox_export_requires_session.",
    "status": "Closed",
    "closedBranch": "fix/board-com-003-through-010",
    "closedDate": "2026-06-04"
  },
  {
    "opportunityId": "COM-008",
    "sourceMeetingId": "MTG-0001",
    "severity": "Medium",
    "gap": "Launcher: stdio-only config triggers unconditional docker run; stopped-container name collision unhandled; tcp_allow_remote config field never read.",
    "requiredAdjustment": "COM-008b: remove --name from client templates; COM-008c: enforce tcp_allow_remote in serve_all; COM-008a: deferred (no launch code exists yet).",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_tcp_allow_remote_false_rejects_non_loopback, test_tcp_allow_remote_true_permits_non_loopback; client templates updated.",
    "status": "Closed",
    "closedBranch": "fix/board-com-003-through-010",
    "closedDate": "2026-06-04",
    "note": "COM-008a deferred to future launcher implementation"
  },
  {
    "opportunityId": "COM-009",
    "sourceMeetingId": "MTG-0001",
    "severity": "Medium",
    "gap": "SessionManager multi-profile storage vs. single-session API. session_status() non-deterministic with multiple profiles.",
    "requiredAdjustment": "PQ-001 Option A: single-session semantics, implicit replace on session_start.",
    "owner": "Chris Slothouber",
    "targetWindow": "Chunk 1.3 window",
    "closureEvidence": "test_session_status_uses_default_profile, test_session_start_replaces_active_session. PQ-001 closed.",
    "status": "Closed",
    "closedBranch": "fix/board-com-003-through-010",
    "closedDate": "2026-06-04"
  },
  {
    "opportunityId": "COM-010",
    "sourceMeetingId": "MTG-0001",
    "severity": "Low",
    "gap": "CLI top-level --transports flag duplicates serve --transports subcommand. No docs. Confuses integrators.",
    "requiredAdjustment": "Remove top-level --transports before 1.4.",
    "owner": "Chris Slothouber",
    "targetWindow": "Before 1.4",
    "closureEvidence": "test_top_level_transports_flag_rejected, test_serve_transports_flag_accepted.",
    "status": "Closed",
    "closedBranch": "fix/board-com-003-through-010",
    "closedDate": "2026-06-04"
  }
]
```

---

## Closure Summary

- Closed this cycle: **10** (COM-001 through COM-010)
  - COM-001, COM-002: PR #4, 2026-06-04
  - COM-003 through COM-010: branch `fix/board-com-003-through-010`, 2026-06-04
- Deferred this cycle: 1 sub-item (COM-008a — launcher docker run guard; no launch code exists yet)
- Rejected this cycle: 0
- Open critical blockers: **0**
- Open high blockers: **0** — chunk 1.4 gate cleared
- Open medium: **0**
- Open low: **0**
- **All COM items resolved. Ready for chunk 1.4.**
