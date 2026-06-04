# Chunk 1.1 — Core Implementation

**Status:** Planned
**Depends on:** 1.0 closed (`ed0e5fb` on `main`); CI green on skeleton.
**Risk tier:** Medium

## Purpose

Wire the three real subsystems that back every `BrokerCore` method:
`SessionManager` (pyocd/openocd gdbserver subprocess supervisor),
`LaneSupervisor` (swd + itm_swo lane state), and `BrokerCore` itself
(dispatches into both, owns the operation audit log). Replace every
`NotImplementedError` stub with callable code and a full unit-test suite
that mocks the subprocess layer. Hardware integration tests are authored
here but gated behind `pytest -m hardware`, excluded from CI (risk R9).

## Scope

### In scope

- **`SessionManager`** (`core/session.py`) — real implementation
  extracted from cockpit's `DebugSessionManager`:
  - `start(**kwargs)` — accepts `target`, `probe_uid`, `pack`,
    `frequency_hz`, `backend` (`pyocd`|`openocd`), `gdb_port`,
    `pyocd_bin`, `gdb_bin`, `extra_args`. Spawns pyocd/openocd
    gdbserver subprocess (`start_new_session=True`). Waits for TCP
    readiness on `gdb_port` (poll-with-timeout). Writes session
    metadata JSON. Returns `SessionStatus`.
  - `stop(force)` — SIGTERM → wait → SIGKILL fallback. Removes
    metadata file. Returns `SessionStatus`.
  - `status()` — reads metadata JSON; probes TCP port; derives
    `state ∈ {stopped, healthy, unhealthy, stale}`. Returns
    `SessionStatus`.
  - Session metadata persisted at
    `$PROBE_BROKER_LOG_DIR/<profile>.json`.
  - No `HilProfile` dependency — all inputs are explicit kwargs.
  - Operation-lock guard (O_CREAT|O_EXCL on `.lock.json`) prevents
    concurrent `start`/`stop` calls from racing.

- **`ItmSwoLane`** (`core/lanes.py`) — real implementation:
  - `start(ports, cpu_clock_hz, trace_clock_hz)` — records active
    ITM streaming state; returns `ItmStreamHandle`.
  - `stop()` — clears state; returns `ItmStreamSummary`.

- **`LaneSupervisor`** (`core/lanes.py`) — real implementation:
  - Manages `swd` and `itm_swo` lanes from `BrokerConfig.lanes`.
  - `lane_status()` — returns `dict[str, LaneStatus]` keyed by
    enabled lane names.
  - `lane_release(lane)` / `lane_resume(lane)` — records released /
    resumed state on the named lane; returns `LaneStatus`.

- **`BrokerCore`** (`core/broker.py`) — all 15 methods implemented:

  | Method | Backend |
  |---|---|
  | `session_start(**kwargs)` | `SessionManager.start` |
  | `session_stop(force)` | `SessionManager.stop` |
  | `session_status()` | `SessionManager.status` → `SessionStatus` |
  | `halt()` | GDB `monitor halt`; returns `ProbeState` |
  | `resume(disconnect_gdb)` | GDB `continue& / disconnect`; returns `ProbeState` |
  | `reset(kind, halt_after)` | GDB `monitor reset` ± `monitor halt`; returns `ProbeState` |
  | `program(artifact, format, address, halt_after, reset_after)` | GDB `monitor halt` + `load` + `monitor reset`; returns `ProgramResult` |
  | `mem_read(addr, length, format)` | GDB `x/<n>wx`; parses output; returns `MemReadResult` |
  | `blackbox_export(out)` | `pyocd` subprocess dump; returns `BlackboxExportResult` |
  | `itm_stream_start(ports, cpu_clock_hz, trace_clock_hz)` | `LaneSupervisor.itm_swo.start` |
  | `itm_stream_stop()` | `LaneSupervisor.itm_swo.stop` |
  | `lane_status()` | `LaneSupervisor.lane_status` |
  | `lane_release(lane)` | `LaneSupervisor.lane_release` |
  | `lane_resume(lane)` | `LaneSupervisor.lane_resume` |
  | `recent_lines(since_seq, limit)` | In-memory `deque`; returns `list[LogLine]` |

  GDB dispatch uses a single `_run_gdb(commands, symbol_file)` helper
  that builds `[gdb_bin, --batch, -ex connect, -ex cmd, …]` and calls
  `subprocess.run`. Every method appends to the operation audit log
  (`deque(maxlen=256)`); `recent_lines` filters and slices it.

- **`BrokerConfig`** additions (if needed) — no new fields expected;
  existing `pyocd_bin`, `gdb_bin`, `gdb_port`, `log_dir`,
  `enable_swv` are sufficient. Update if gap found.

- **`models.py`** — `SessionStatus.state` documented as
  `stopped | healthy | unhealthy | stale`. No new model fields
  expected; update if gap found.

- **Test suite** — replaces all `NotImplementedError` tests with
  real unit tests:
  - `tests/test_session_manager.py` — lifecycle: start (mock Popen +
    TCP probe), stop (mock SIGTERM), status (stopped/healthy/stale
    states). Operation lock contention test.
  - `tests/test_lanes.py` — `ItmSwoLane` start/stop, `LaneSupervisor`
    lane_status/release/resume for both swd and itm_swo.
  - `tests/test_broker_core.py` — each of the 15 methods; mocks
    `subprocess.run` and `subprocess.Popen`; asserts result model
    shape.
  - `tests/test_broker_not_implemented.py` — **deleted**; all methods
    now callable.
  - `tests/hardware/test_hardware_session.py` — marked
    `@pytest.mark.hardware`; not run in CI; requires a physical SWD
    target (STM32 or similar).

- **`pyproject.toml`** — add `pyocd` as runtime dependency with a
  pinned minor version (e.g. `pyocd>=0.36,<0.37`) per risk R2. Add
  `pytest-mock` to `[dev]` extra.

- **Branch:** `core/session-lane-broker-impl` — off `main` at
  `bc6c3d9` (planning scaffold commit).

- **Evidence:** `artifacts/validation/phase-1/chunk-1.1/run_<UTC>/`

### Out of scope

- Transport adapter implementations (stdio MCP server, socket, TCP
  listener) — chunk 1.2.
- Flock + try-connect + named-container singleton launcher — chunk 1.2.
- Dockerfile / docker-compose / cosign signing — chunk 1.3.
- Real ITM/SWO data capture from the pyocd SWV raw port — deferred;
  `itm_stream_start` records intent only in 1.1; actual byte-stream
  consumption is a post-1.x enhancement.
- Multi-probe arbitration — out of phase entirely (§ 8 of protocol
  spec).

## Key Design Decisions

1. **No `HilProfile` import.** All session kwargs are explicit;
   cockpit's `HilProfile` stays in cockpit. The facade supplies them
   when calling `session_start`.

2. **GDB over subprocess, not pygdbmi.** Matches cockpit's proven
   approach; avoids a new dependency in 1.1. `pygdbmi` or pyocd's
   Python API are Phase 2 candidates if MI parsing becomes necessary.

3. **`subprocess.run` is the injection seam.** `BrokerCore.__init__`
   accepts optional `_subprocess_run` and `_subprocess_popen`
   overrides (defaulting to `subprocess.run` and `subprocess.Popen`)
   so unit tests can mock without `pytest-mock` monkeypatching.

4. **Session metadata format.** JSON file at
   `$PROBE_BROKER_LOG_DIR/<sanitised-profile>.json` — same schema as
   cockpit's `DebugSessionManager`. Fields: `backend`, `pid`,
   `process_group_id`, `gdb_host`, `gdb_port`, `log_path`,
   `started_epoch_s`.

5. **Operation audit log.** `deque(maxlen=256)` on `BrokerCore`;
   each entry matches `LogLine` model fields. `recent_lines` returns a
   filtered, sliced copy (thread-safe under `threading.Lock`).

6. **`pyocd` pin.** Pinned `>=0.36,<0.37` at 1.1 open time. Update
   the upper bound each release if tests pass (risk R2).

## Acceptance Criteria

| ID | Criterion |
|---|---|
| `SCN-1.1-NO-NIE` | `grep -r "NotImplementedError" src/brontes_probe_mcp/core/` returns empty (transport stubs in `transports/` are 1.2 scope). |
| `SCN-1.1-TEST-COUNT` | `pytest --collect-only -q` collects ≥ 60 tests (up from 40). |
| `SCN-1.1-SESSION-LIFECYCLE` | `test_session_manager.py::test_start_stop_cycle` passes with mocked Popen. |
| `SCN-1.1-LANE-STATUS` | `test_lanes.py::test_lane_status_both_lanes` returns `{"swd": ..., "itm_swo": ...}` when both lanes enabled. |
| `SCN-1.1-BROKER-METHODS` | All 15 `BrokerCore` method tests pass; each asserts correct Pydantic result model type. |
| `SCN-1.1-RECENT-LINES` | `test_broker_core.py::test_recent_lines_after_halt` confirms audit entry present with correct `method` field. |
| `SCN-1.1-CI` | All 4 CI matrix cells green (ubuntu-22.04 + macos-14 × 3.11 + 3.12). |
| `SCN-1.1-MYPY` | `mypy --strict src/` exits 0. |
| `SCN-1.1-PYOCD-PIN` | `pyocd>=0.36,<0.37` (or current tested minor) present in `pyproject.toml` `[project.dependencies]`. |
| `SCN-1.1-HW-MARKER` | `tests/hardware/` exists; hardware tests carry `@pytest.mark.hardware`; `pytest -m "not hardware"` collects none from that directory. |

## Risks Activated

- **R2 (pyocd API instability)** — active. Mitigated by pinning.
  CI will surface breakage on minor-version bump.
- **R9 (hardware-in-the-loop flakiness)** — active. Mitigated by
  `pytest -m hardware` exclusion from CI matrix. Hardware tests run
  manually pre-release.

## File Map

New:
- `tests/test_session_manager.py`
- `tests/test_lanes.py`
- `tests/test_broker_core.py`
- `tests/hardware/__init__.py`
- `tests/hardware/test_hardware_session.py`
- `artifacts/validation/phase-1/chunk-1.1/run_<UTC>/chunk_1_1_record.md`

Modified:
- `src/brontes_probe_mcp/core/session.py` — full implementation
- `src/brontes_probe_mcp/core/lanes.py` — full implementation
- `src/brontes_probe_mcp/core/broker.py` — full implementation
- `src/brontes_probe_mcp/core/models.py` — doc `SessionStatus.state`
  values if not already done
- `pyproject.toml` — add `pyocd` runtime dep, `pytest-mock` dev dep

Deleted:
- `tests/test_broker_not_implemented.py`

## Verification Plan

1. `python -m pytest -m "not hardware" --tb=short` — all pass.
2. `mypy --strict src/brontes_probe_mcp/` — exits 0.
3. `ruff check src/ tests/` — exits 0.
4. `grep -r "NotImplementedError" src/` — empty.
5. `python -m pytest --collect-only -q | tail -1` — confirms ≥ 60
   tests collected.

## Rollback

`git revert` the chunk-1.1 squash-merge commit. `NotImplementedError`
stubs are gone, so rollback restores the state to chunk-1.0 HEAD
(`ed0e5fb`). No external systems affected (no container, no transport
listener, no released version).

## Open Questions

*(None at plan time. Add YAML files in `docs/planning/pool_questions/`
if questions arise during implementation.)*
