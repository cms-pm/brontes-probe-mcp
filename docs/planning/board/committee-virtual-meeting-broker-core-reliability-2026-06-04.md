# Board Review Meeting — Broker Core Reliability
# Ad-Hoc Sprint Critique — 2026-06-04

## Status
Closed (findings adopted, gate decision issued)

## Date
2026-06-04

## Positioning Note
This is a **simulated** board review. The review panel role was performed by
the delivery AI (Claude Sonnet 4.6) acting as devil's advocate immediately
after chunk 1.2 implementation and prior to the 1.2 merge gate. This exercise
is not authored or endorsed by external individuals.

## Machine-Readable Metadata (YAML)

```yaml
meetingId: MTG-0001
boardId: BRD-2026-06
cadenceLane: Sprint Critique
riskTierFocus:
  - critical
  - high
  - medium
trigger: ad-hoc — chunk 1.2 delivery, board-review gate waived by chair in favour of devil's-advocate review
packetRef: docs/planning/board/committee-virtual-meeting-broker-core-reliability-2026-06-04.md
```

## Meeting Cadence Lane
Sprint Critique (ad-hoc, triggered by chunk 1.2 delivery + board-review gate)

## Chair and Participants
- Chairperson: Chris Slothouber
- Review Panel: Claude Sonnet 4.6 (delivery AI, devil's-advocate lens)
- Domain Owner: Chris Slothouber (BrokerCore, SessionManager, transports, launcher)
- Scribe: Claude Sonnet 4.6

## Objective
Identify blind spots and reliability risks in the chunk 1.1 + 1.2 implementation
before chunk 1.3 (container + signing) begins. Produce a prioritised finding set
that gates the 1.4 first release. Waived formal board composition in favour of
immediate devil's-advocate analysis; findings carry the same normative weight.

## Packet Presented (Pre-Read)
1. `docs/planning/PHASE_1_TODO.md` — phase roadmap and gate posture
2. `docs/planning/phase-1-risks.md` — existing risk register (R1–R9)
3. PR #3 diff: `transports/adapters-and-launcher` — chunk 1.2 implementation
4. Source: `src/brontes_probe_mcp/core/{broker,session,lanes,models}.py`
5. Source: `src/brontes_probe_mcp/{launcher,transports/*.py}`
6. Prior action closure: 3 review fixes applied (signal side-effect, TCP token pre-validation, kwargs mutation)

## Agenda
1. Context and objective recap
2. Evidence review — core broker methods
3. Evidence review — session and lane management
4. Evidence review — launcher
5. Evidence review — test coverage and assumptions
6. Finding triage and severity classification
7. Go/No-Go and gate decision

---

## Constructive Criticism Log

| ID | Observation | Risk/Gap | Severity | Required Adjustment | Closure Evidence | Owner | Target Window |
|---|---|---|---|---|---|---|---|
| FND-001 | `_run_gdb` uses `check=False`, discards stderr entirely, and always returns stdout. Every probe op (halt, resume, reset, mem_read, program) returns a success-shaped model regardless of actual GDB outcome. | An MCP client gets `{"halted": true}` even when no probe is connected. Silent success on disconnect is the worst possible failure mode for a remote debug tool. | **Critical** | Inspect `returncode` and stderr in `_run_gdb`; raise a descriptive exception on failure. Let `dispatch`/`_call_handler` surface it as `broker_internal_error`. | `tests/test_broker_core.py` gains a test asserting that a GDB non-zero exit maps to an error response; existing mock already controls returncode. | Chris Slothouber | Before chunk 1.3 starts |
| FND-002 | `halt()`, `resume()`, `reset()`, `mem_read()`, `program()` execute unconditionally. `session_status().state` is never consulted before issuing GDB commands. | Calling any probe op before `session_start` (or after `session_stop`) silently "succeeds". Clients cannot distinguish "probe halted" from "GDB not running". | **Critical** | Add a session-state guard in `BrokerCore` (or at `_run_gdb` callsites) that raises if no healthy session is active. Alternatively, surface a dedicated error shape (`session_required`). | Test asserting that `halt()` on a broker with no active session returns an error response. | Chris Slothouber | Before chunk 1.3 starts |
| FND-003 | `MemReadResult.value: str` is raw GDB dump text (e.g. `"0x20000000:\t0x00000000\n"`). The `format` parameter (`"hex"` / `"bytes"`) is accepted but does nothing — implementation ignores it. `program()` reports `artifact.stat().st_size` (file size) as `programmed_bytes`, not bytes flashed. | Clients that parse `value` as structured hex will get garbage. The `format` parameter in the MCP schema creates a false contract. `programmed_bytes` misleads on ELF files with small `.text` sections. | **High** | Parse GDB `x/wx` output into a list of hex words. Honour `format`: `"hex"` → list of `"0xDEADBEEF"` strings; `"bytes"` → base64 or byte list. `programmed_bytes` should parse GDB `load` output for actual transferred bytes. | `test_mem_read_format_hex` and `test_mem_read_format_bytes` assertions on value shape. `test_program_bytes` verifies `programmed_bytes` reflects flash size not file size. | Chris Slothouber | Chunk 1.3 window |
| FND-004 | `LaneSupervisor._lane_states` (plain dict) and `ItmSwoLane._active`/`_ports` have no mutex. Three concurrent transport threads share one `BrokerCore`. | Concurrent `lane_release` + `lane_resume` from socket and TCP transports is an unguarded dict mutation — a data race. `ItmSwoLane` state similarly unprotected. | **High** | Add `threading.Lock` (or `threading.RLock`) to `LaneSupervisor` guarding `_lane_states` mutations and reads. Add equivalent lock to `ItmSwoLane`. | Existing parity tests cover concurrent dispatch paths; a dedicated concurrent-mutation test under `threading` confirms no torn state. | Chris Slothouber | Chunk 1.3 window |
| FND-005 | `SessionManager.start()` records `process_group_id` and uses `start_new_session=True`. `stop()` calls `os.kill(pid, sig)` only — ignoring the recorded PGID. pyocd spawns child processes. | On `session_stop`, child processes (OpenOCD, libusb workers) survive. Over time these accumulate, holding USB device handles, preventing re-attach. | **High** | Replace `os.kill(pid, sig)` with `os.killpg(pgid, sig)` in `stop()`, reading `process_group_id` from meta. Fall back to `os.kill(pid, sig)` if PGID is missing. | `test_session_stop_kills_process_group` verifies `os.killpg` is called with the recorded PGID. | Chris Slothouber | Chunk 1.3 window |
| FND-006 | `_OperationLock` uses `O_CREAT|O_EXCL` (correct for mutual exclusion) but has no stale-lock detection. A crash while holding the lock leaves the file permanently; every subsequent `session_start`/`session_stop` raises `"Session operation in progress"`. | Users have no recovery path except manual `rm`. This is a silent self-inflicted DoS after any crash. No timeout, no CLI diagnostic. | **Medium** | Add stale-lock detection: check file mtime; if older than a configured threshold (e.g. 30 s), unlink and re-acquire. Document the manual recovery path in ops runbook. Expose a `session_unlock` CLI command. | Test simulating crash (close fd without unlink, then attempt re-acquire after threshold) confirms auto-recovery. | Chris Slothouber | Chunk 1.3 window |
| FND-007 | `blackbox_export` calls `pyocd pack export -o <out>`. This subcommand does not exist in pyocd. `check=False` swallows the error; `bytes_written=0` is returned silently. | Every call to `blackbox_export` fails invisibly. The MCP tool reports success with 0 bytes. | **Medium** | Determine the correct pyocd command for snapshot/export (or document as unimplemented). If unimplemented, return a structured `not_implemented` error rather than a zero-byte success. | Test asserting that a pyocd exit-1 on `blackbox_export` produces an error response (not a success with `bytes_written=0`). | Chris Slothouber | Chunk 1.3 window |
| FND-008 | `launcher.py`: (a) stdio-only `transports` config skips both socket and TCP checks → `docker run` fires unconditionally on every call. (b) `--name brontes-probe-mcp` with no `--rm` → fails if a stopped container with that name exists. (c) `tcp_allow_remote: bool = False` in `BrokerConfig` is declared but never read. | (a) Repeated docker spawns from stdio-only consumers. (b) Second `launch()` call returns `RuntimeError` from Docker, not a clean "already running". (c) Dead config field creates false security assurance. | **Medium** | (a) If no connectable transport is configured, skip the try-connect step and proceed to docker. (b) Add `docker rm -f brontes-probe-mcp || true` before `docker run`, or use `docker start` if stopped. (c) Either enforce `tcp_allow_remote` by binding to `0.0.0.0` only when `True`, or remove the field. | Launcher test covering stopped-container scenario; test confirming `tcp_allow_remote=False` refuses non-loopback binds. | Chris Slothouber | Chunk 1.3 window |
| FND-009 | `SessionManager` writes one `.json` profile per target (multi-profile storage). `session_status()` returns only the first profile found. `session_stop()` kills all profiles. The protocol API (and `BrokerCore`) present single-session semantics. | Multi-profile storage is either vestigial (and therefore wasted complexity) or the protocol spec intends something the implementation doesn't support. When two targets are active, `session_status()` returns an arbitrary one. | **Medium** | Clarify intent against the protocol spec. If single-session: simplify storage to one fixed profile path. If multi-session: add a `target` param to `session_status` and `session_stop`. Pool-question candidate. | ADR or pool-question closure resolving single vs. multi-session; implementation updated accordingly; test covering the clarified semantics. | Chris Slothouber | Chunk 1.3 window |
| FND-010 | `cli.py` has two execution paths that both invoke `serve_all`: the `serve` subcommand and the legacy top-level `--transports` flag. Neither is documented relative to the other. | CLI surface ambiguity; `--help` output suggests two equivalent entry points. Legacy path is not tested independently and will confuse integrators. | **Low** | Remove top-level `--transports` path. The `serve` subcommand is the supported surface. | `test_cli.py` confirms `--transports` at top level is no longer valid; `serve --transports` continues to pass. | Chris Slothouber | Before 1.4 |

---

## Structured Findings (JSON)

```json
[
  {
    "findingId": "FND-001",
    "meetingId": "MTG-0001",
    "severity": "Critical",
    "lens": "reliability",
    "observation": "_run_gdb uses check=False, discards stderr, and returns stdout unconditionally. All probe operations (halt, resume, reset, mem_read, program) return a success-shaped Pydantic model regardless of actual GDB outcome.",
    "riskGap": "Silent success on GDB failure is the worst possible failure mode for a remote debug tool. An MCP client gets {halted: true} even when no probe is connected.",
    "requiredAdjustment": "Inspect returncode and stderr in _run_gdb; raise a descriptive exception on failure. Let dispatch/_call_handler surface it as broker_internal_error.",
    "closureEvidence": "tests/test_broker_core.py: test asserting GDB non-zero exit maps to error response shape.",
    "owner": "Chris Slothouber",
    "targetDate": "Before chunk 1.3 starts",
    "status": "open"
  },
  {
    "findingId": "FND-002",
    "meetingId": "MTG-0001",
    "severity": "Critical",
    "lens": "reliability",
    "observation": "halt(), resume(), reset(), mem_read(), program() execute unconditionally. session_status().state is never consulted before issuing GDB commands.",
    "riskGap": "Calling any probe op before session_start silently succeeds. Clients cannot distinguish a real probe state from GDB-not-running.",
    "requiredAdjustment": "Add a session-state guard in BrokerCore or at _run_gdb callsites that raises if no healthy session is active. Surface a session_required error shape.",
    "closureEvidence": "test asserting halt() on a broker with state != healthy returns error response with kind=session_required.",
    "owner": "Chris Slothouber",
    "targetDate": "Before chunk 1.3 starts",
    "status": "open"
  },
  {
    "findingId": "FND-003",
    "meetingId": "MTG-0001",
    "severity": "High",
    "lens": "reliability",
    "observation": "MemReadResult.value is raw GDB dump text. The format parameter (hex/bytes) is ignored. program() reports artifact file size as programmed_bytes, not actual flash bytes.",
    "riskGap": "Clients parsing value as structured data get garbage. format creates a false API contract. programmed_bytes misleads on ELF files.",
    "requiredAdjustment": "Parse GDB x/wx output into structured format per the format parameter. Parse GDB load output for programmed_bytes.",
    "closureEvidence": "test_mem_read_format_hex and test_mem_read_format_bytes assert value shape. test_program_bytes verifies programmed_bytes reflects flash not file size.",
    "owner": "Chris Slothouber",
    "targetDate": "Chunk 1.3 window",
    "status": "open"
  },
  {
    "findingId": "FND-004",
    "meetingId": "MTG-0001",
    "severity": "High",
    "lens": "reliability",
    "observation": "LaneSupervisor._lane_states (plain dict) and ItmSwoLane._active/_ports have no mutex. Three concurrent transport threads share one BrokerCore instance.",
    "riskGap": "Concurrent lane_release + lane_resume from socket and TCP transports is an unguarded dict mutation — a data race.",
    "requiredAdjustment": "Add threading.Lock to LaneSupervisor guarding _lane_states mutations and reads. Add equivalent lock to ItmSwoLane.",
    "closureEvidence": "Concurrent-mutation test under threading confirms no torn state across parallel dispatch.",
    "owner": "Chris Slothouber",
    "targetDate": "Chunk 1.3 window",
    "status": "open"
  },
  {
    "findingId": "FND-005",
    "meetingId": "MTG-0001",
    "severity": "High",
    "lens": "operability",
    "observation": "session_stop() calls os.kill(pid, sig) ignoring the process_group_id recorded in meta. start_new_session=True is used at spawn, so pyocd may have children.",
    "riskGap": "Child processes (OpenOCD, libusb workers) survive session_stop. Over time they accumulate, holding USB device handles.",
    "requiredAdjustment": "Replace os.kill(pid, sig) with os.killpg(pgid, sig) in stop(), reading process_group_id from meta. Fall back to os.kill if PGID missing.",
    "closureEvidence": "test_session_stop_kills_process_group verifies os.killpg called with recorded PGID.",
    "owner": "Chris Slothouber",
    "targetDate": "Chunk 1.3 window",
    "status": "open"
  },
  {
    "findingId": "FND-006",
    "meetingId": "MTG-0001",
    "severity": "Medium",
    "lens": "operability",
    "observation": "_OperationLock uses O_CREAT|O_EXCL with no stale-lock detection. A process crash leaves the lock file permanently.",
    "riskGap": "Every subsequent session_start/session_stop raises after a crash. No recovery path except manual rm.",
    "requiredAdjustment": "Add stale-lock detection by mtime threshold. Document manual recovery. Add session_unlock CLI subcommand.",
    "closureEvidence": "Test simulating crash-then-reacquire after threshold confirms auto-recovery.",
    "owner": "Chris Slothouber",
    "targetDate": "Chunk 1.3 window",
    "status": "open"
  },
  {
    "findingId": "FND-007",
    "meetingId": "MTG-0001",
    "severity": "Medium",
    "lens": "reliability",
    "observation": "blackbox_export calls 'pyocd pack export -o <out>' with check=False. This subcommand does not exist in pyocd. Failure is silently swallowed; bytes_written=0 returned.",
    "riskGap": "Every call to blackbox_export fails invisibly. MCP tool reports success with 0 bytes.",
    "requiredAdjustment": "Determine correct pyocd command or mark as not_implemented with a structured error response. Never return success for a zero-byte write.",
    "closureEvidence": "Test asserting pyocd exit-1 on blackbox_export produces error response, not bytes_written=0.",
    "owner": "Chris Slothouber",
    "targetDate": "Chunk 1.3 window",
    "status": "open"
  },
  {
    "findingId": "FND-008",
    "meetingId": "MTG-0001",
    "severity": "Medium",
    "lens": "operability",
    "observation": "launcher.py: stdio-only config triggers docker run unconditionally; --name collision on stopped containers raises RuntimeError; tcp_allow_remote is declared but never enforced.",
    "riskGap": "Repeated docker spawns for stdio-only consumers. Failed second launch() call is unrecoverable without manual docker rm. False security assurance from tcp_allow_remote field.",
    "requiredAdjustment": "Handle stdio-only transport config. Add docker rm -f before run or use docker start. Either enforce tcp_allow_remote or remove it.",
    "closureEvidence": "Launcher tests covering stopped-container and stdio-only scenarios. tcp_allow_remote enforcement test.",
    "owner": "Chris Slothouber",
    "targetDate": "Chunk 1.3 window",
    "status": "open"
  },
  {
    "findingId": "FND-009",
    "meetingId": "MTG-0001",
    "severity": "Medium",
    "lens": "architecture",
    "observation": "SessionManager writes one .json profile per target (multi-profile storage). session_status() returns only the first profile. session_stop() kills all. API surface presents single-session semantics.",
    "riskGap": "Multi-profile storage is either vestigial complexity or the protocol spec intends something the implementation doesn't support. session_status() is non-deterministic when two profiles exist.",
    "requiredAdjustment": "Clarify against protocol spec. If single-session: simplify to one fixed profile. If multi-session: add target param to session_status and session_stop.",
    "closureEvidence": "Pool-question closure or ADR resolving single vs. multi-session semantics. Implementation updated; test covering clarified behaviour.",
    "owner": "Chris Slothouber",
    "targetDate": "Chunk 1.3 window",
    "status": "open"
  },
  {
    "findingId": "FND-010",
    "meetingId": "MTG-0001",
    "severity": "Low",
    "lens": "cognitive-load",
    "observation": "cli.py has two execution paths that both call serve_all: the serve subcommand and the legacy top-level --transports flag.",
    "riskGap": "CLI surface ambiguity. --help suggests two equivalent entry points. Legacy path untested independently.",
    "requiredAdjustment": "Remove top-level --transports path before 1.4. serve subcommand is the supported surface.",
    "closureEvidence": "test_cli.py confirms --transports at top level is rejected; serve --transports continues to pass.",
    "owner": "Chris Slothouber",
    "targetDate": "Before 1.4",
    "status": "open"
  }
]
```

---

## Opportunity Register (Meeting Output)

| ID | Severity | Opportunity / Gap | Immediate Deliverable | Suggested Owner | Target Window | Status |
|---|---|---|---|---|---|---|
| COM-001 | Critical | GDB backend silent failure | `_run_gdb` error propagation + test | Chris Slothouber | Before 1.3 | Adopted |
| COM-002 | Critical | No session guard on probe ops | Session-state check at `_run_gdb` + test | Chris Slothouber | Before 1.3 | Adopted |
| COM-003 | High | `MemReadResult.value` unstructured; `format` ignored | GDB output parsing; honour format param | Chris Slothouber | Chunk 1.3 window | Adopted |
| COM-004 | High | `LaneSupervisor`/`ItmSwoLane` thread-unsafe | Add `threading.Lock` to lane state mutations | Chris Slothouber | Chunk 1.3 window | Adopted |
| COM-005 | High | `session_stop` ignores PGID — child process leak | Use `os.killpg` from recorded PGID | Chris Slothouber | Chunk 1.3 window | Adopted |
| COM-006 | Medium | `_OperationLock` no stale-lock recovery | mtime-based stale detection + `session_unlock` CLI | Chris Slothouber | Chunk 1.3 window | Adopted |
| COM-007 | Medium | `blackbox_export` calls non-existent pyocd command | Correct command or structured not-implemented error | Chris Slothouber | Chunk 1.3 window | Adopted |
| COM-008 | Medium | Launcher: stdio-only, stopped-container, dead config field | Three targeted launcher fixes | Chris Slothouber | Chunk 1.3 window | Adopted |
| COM-009 | Medium | Multi-session storage vs. single-session API ambiguity | Pool question → ADR → impl update | Chris Slothouber | Chunk 1.3 window | Adopted |
| COM-010 | Low | CLI duplicate serve path | Remove top-level `--transports` | Chris Slothouber | Before 1.4 | Adopted |

---

## Structured Decisions (JSON)

```json
[
  {
    "decisionId": "DEC-001",
    "meetingId": "MTG-0001",
    "relatedFindingIds": ["FND-001", "FND-002"],
    "outcome": "Adopted",
    "rationale": "GDB silent failure and absent session guard are release-blocking. Both must be resolved before chunk 1.3 begins. PR #3 may merge because these defects originate in chunk 1.1 (core implementation), not in the transport layer delivered by 1.2.",
    "gate": {
      "scopeDecision": "Conditional-Go on PR #3",
      "gateStatement": "PR #3 (chunk 1.2) may merge. FND-001 and FND-002 must close before chunk 1.3 is marked in-progress.",
      "preconditions": [
        "FND-001: _run_gdb raises on GDB failure; test coverage added",
        "FND-002: session guard at probe op entry points; test coverage added"
      ]
    }
  },
  {
    "decisionId": "DEC-002",
    "meetingId": "MTG-0001",
    "relatedFindingIds": ["FND-003", "FND-004", "FND-005", "FND-006", "FND-007", "FND-008", "FND-009"],
    "outcome": "Adopted",
    "rationale": "High and medium findings are pre-release blockers but do not block chunk 1.3 start. They must close before the 1.4 release gate. Best addressed as a dedicated pre-1.3 or early-1.3 fix pass rather than deferred to 1.4 scope.",
    "gate": {
      "scopeDecision": "Deferred to chunk 1.3 window",
      "gateStatement": "All high/medium findings must close before 1.4 release gate. Evidence paths defined in opportunity register.",
      "preconditions": [
        "COM-003 through COM-009 closed with test evidence before 1.4 release gate"
      ]
    }
  },
  {
    "decisionId": "DEC-003",
    "meetingId": "MTG-0001",
    "relatedFindingIds": ["FND-010"],
    "outcome": "Adopted",
    "rationale": "Low severity; no test coverage impact. Remove before 1.4 to clean the CLI surface before public release.",
    "gate": {
      "scopeDecision": "Deferred to pre-1.4",
      "gateStatement": "FND-010 must close before 1.4 tag.",
      "preconditions": ["COM-010 closed"]
    }
  }
]
```

---

## Go / No-Go Decision

- **Scope decision:** Conditional-Go (PR #3 / chunk 1.2)
- **Gate statement:** PR #3 may merge. Two Critical findings (FND-001, FND-002) must close before chunk 1.3 is opened. Seven high/medium findings must close before the 1.4 release gate.
- **Preconditions for 1.3 start:**
  1. FND-001 closed — `_run_gdb` propagates GDB errors; test evidence in `tests/test_broker_core.py`
  2. FND-002 closed — session guard at probe op entry; `kind: session_required` error shape; test evidence
- **Preconditions for 1.4 release gate:**
  3. COM-003 through COM-009 all closed with test evidence
  4. COM-010 closed (CLI legacy path removed)

---

## Integration Targets

1. `docs/planning/board/committee-opportunity-register-broker-core-reliability-2026-06-04.md` — full register
2. `docs/planning/phase-1-risks.md` — add R10–R14 for findings that cross risk tiers
3. `docs/planning/pool_questions/PQ-001-session-single-vs-multi-profile.md` — FND-009 pool question
4. `docs/planning/chunks/phase-1/chunk-1.3-container-and-signing.md` — prepend reliability fix obligations as pre-start gate
5. `artifacts/validation/phase-1/chunk-1.2/` — link this meeting record as board evidence for 1.2 gate

---

## Action Register

| Action ID | Description | Owner | Due Date | Evidence Path | Status |
|---|---|---|---|---|---|
| ACT-001 | Close FND-001: `_run_gdb` error propagation + test | Chris Slothouber | Before 1.3 opens | `tests/test_broker_core.py` | Open |
| ACT-002 | Close FND-002: session guard + `session_required` error shape + test | Chris Slothouber | Before 1.3 opens | `tests/test_broker_core.py` | Open |
| ACT-003 | Close FND-003: GDB output parsing for `mem_read`; `programmed_bytes` from load output | Chris Slothouber | Chunk 1.3 window | `tests/test_broker_core.py` | Open |
| ACT-004 | Close FND-004: add `threading.Lock` to `LaneSupervisor` and `ItmSwoLane` | Chris Slothouber | Chunk 1.3 window | `tests/test_lanes.py` | Open |
| ACT-005 | Close FND-005: use `os.killpg` from recorded PGID in `session_stop` | Chris Slothouber | Chunk 1.3 window | `tests/test_session_manager.py` | Open |
| ACT-006 | Close FND-006: stale-lock detection + `session_unlock` CLI subcommand | Chris Slothouber | Chunk 1.3 window | `tests/test_session_manager.py` | Open |
| ACT-007 | Close FND-007: correct `blackbox_export` command or not-implemented error | Chris Slothouber | Chunk 1.3 window | `tests/test_broker_core.py` | Open |
| ACT-008 | Close FND-008: three launcher fixes (stdio-only, stopped-container, tcp_allow_remote) | Chris Slothouber | Chunk 1.3 window | `tests/test_launcher.py` | Open |
| ACT-009 | Open pool question PQ-001 for FND-009 single vs. multi-session | Chris Slothouber | Chunk 1.3 window | `docs/planning/pool_questions/PQ-001-session-single-vs-multi-profile.md` | Open |
| ACT-010 | Close FND-010: remove top-level `--transports` CLI path | Chris Slothouber | Before 1.4 | `tests/test_cli.py` | Open |

---

## Implementation Handoff (JSON)

```json
{
  "handoffId": "HOF-0001",
  "sourceMeetingId": "MTG-0001",
  "riskTier": "critical",
  "adoptedActionIds": ["ACT-001", "ACT-002", "ACT-003", "ACT-004", "ACT-005", "ACT-006", "ACT-007", "ACT-008", "ACT-009", "ACT-010"],
  "chunkMappings": [
    {"actionId": "ACT-001", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-002", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-003", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-004", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-005", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-006", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-007", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-008", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-009", "chunkId": "pre-1.3-reliability-fixes"},
    {"actionId": "ACT-010", "chunkId": "pre-1.4-cleanup"}
  ],
  "riskDeltaPaths": ["docs/planning/phase-1-risks.md"],
  "traceabilityPath": "artifacts/validation/phase-1/chunk-1.2/",
  "owner": "Chris Slothouber",
  "status": "ready"
}
```

---

## Ambiguity and Follow-Up Questions

1. **PQ-001** (FND-009): Does the protocol spec intend single-session or multi-session (multi-target) semantics? The storage layer is multi-profile but the query API is single-session. Resolution needed before correcting `SessionManager`.
2. **PQ-002** (FND-007): What is the correct pyocd command for a blackbox/snapshot export? Or is this capability deferred to a post-1.x enhancement? If deferred, `blackbox_export` should return `kind: not_implemented`.
3. **PQ-003** (FND-003): What is the expected shape of `MemReadResult.value` per the protocol spec? List of hex words, flat hex string, base64 bytes? Needs spec clarification before implementation.

---

## Signoff

- Prepared by: Claude Sonnet 4.6 (delivery AI, devil's-advocate lens)
- Reviewed by Chair: Chris Slothouber
- Board/Committee status: **Conditional — go on PR #3 merge; FND-001 and FND-002 gate 1.3 start**

## Post-Meeting Checklist
- [x] Meeting notes published (`docs/planning/board/committee-virtual-meeting-broker-core-reliability-2026-06-04.md`)
- [x] Opportunity register created (`docs/planning/board/committee-opportunity-register-broker-core-reliability-2026-06-04.md`)
- [x] Risk log updated (`docs/planning/phase-1-risks.md` — R10–R14 added)
- [x] Pool question PQ-001 created (FND-009 single vs. multi-session)
- [x] Pool question PQ-002 created (FND-007 blackbox_export correct command)
- [x] Pool question PQ-003 created (FND-003 MemReadResult.value shape)
- [ ] Chunk 1.3 plan updated with pre-start gate (ACT-001, ACT-002)
- [ ] 1.2 evidence dir updated with board meeting link
