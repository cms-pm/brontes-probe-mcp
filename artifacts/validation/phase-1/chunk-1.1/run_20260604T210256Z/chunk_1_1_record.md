# Chunk 1.1 Validation Record

**Run:** 2026-06-04T21:02:56Z  
**Branch:** `core/session-lane-broker-impl`  
**Status:** PASS

## Acceptance Criteria

| ID | Criterion | Result |
|---|---|---|
| `SCN-1.1-NO-NIE` | `grep -r "NotImplementedError" src/brontes_probe_mcp/core/` → empty | PASS |
| `SCN-1.1-TEST-COUNT` | ≥ 60 tests collected | PASS (78 collected) |
| `SCN-1.1-SESSION-LIFECYCLE` | `test_session_manager.py::test_start_stop_cycle` passes | PASS |
| `SCN-1.1-LANE-STATUS` | `test_lanes.py::test_lane_status_both_lanes` returns `{"swd": ..., "itm_swo": ...}` | PASS |
| `SCN-1.1-BROKER-METHODS` | All 15 `BrokerCore` method tests pass | PASS |
| `SCN-1.1-RECENT-LINES` | `test_broker_core.py::test_recent_lines_after_halt` audit entry with correct `method` field | PASS |
| `SCN-1.1-CI` | All 4 CI matrix cells green | Pending (PR not yet merged) |
| `SCN-1.1-MYPY` | `mypy --strict src/brontes_probe_mcp/` exits 0 | PASS |
| `SCN-1.1-PYOCD-PIN` | `pyocd>=0.36,<0.37` in `pyproject.toml` | PASS |
| `SCN-1.1-HW-MARKER` | `tests/hardware/` exists; `pytest -m "not hardware"` excludes them | PASS (3 deselected) |

## Verification Output

```
.......................................................................
75 passed, 3 deselected in 6.85s

mypy --strict src/brontes_probe_mcp/: Success: no issues found in 13 source files
ruff check src/ tests/: All checks passed!
```

## Files Changed

- `src/brontes_probe_mcp/core/session.py` — full `SessionManager` (spawn, poll, SIGTERM/SIGKILL, meta JSON, O_CREAT lock)
- `src/brontes_probe_mcp/core/lanes.py` — `ItmSwoLane` + `LaneSupervisor` real state
- `src/brontes_probe_mcp/core/broker.py` — all 15 `BrokerCore` methods; `deque(maxlen=256)` audit log; subprocess injection seam
- `src/brontes_probe_mcp/core/models.py` — `SessionStatus.state` typed as `Literal[...]`
- `pyproject.toml` — `pyocd>=0.36,<0.37`; `pytest-mock>=3.14`; hardware marker config
- `tests/test_session_manager.py` — 10 tests
- `tests/test_lanes.py` — 14 tests
- `tests/test_broker_core.py` — 23 tests
- `tests/hardware/__init__.py` + `tests/hardware/test_hardware_session.py` — 3 @pytest.mark.hardware
- `tests/test_broker_not_implemented.py` — deleted

## Notes

- `subprocess.run` / `subprocess.Popen` are injectable via `BrokerCore.__init__` for unit-test isolation.
- `SessionManager._tcp_ready` is a patchable method (monkeypatch in tests) to avoid 10s timeout.
- Transport stubs in `transports/` remain as-is (1.2 scope; `NotImplementedError("8.7.2c implementation")`).
