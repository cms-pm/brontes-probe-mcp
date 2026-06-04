# Chunk 1.2 — Transport Adapters + Launcher

**Status:** Planned
**Depends on:** 1.1 closed; full pyocd unit-test suite green.
**Risk tier:** High — tri-transport concurrency is the highest blast-radius
change before release. **Board-review trigger.**

## Purpose

Wire all three transport adapters as concurrent listener threads over
the single shared `BrokerCore` instance. Author the flock +
try-connect + named-container singleton launcher. Demonstrate parity
across all three transports with a tri-transport parity test suite.

## Scope

### In scope

- **MCP stdio adapter** (`transports/stdio.py`):
  - Async `mcp.server.Server` + `stdio_server()` context per the
    graphify idiom (ADG reference).
  - 14 tools registered via `@server.list_tools()` and
    `@server.call_tool()`.
  - Each handler validates kwargs via the corresponding Pydantic model,
    calls `BrokerCore.<method>(**kwargs)`, serialises result to
    `[types.TextContent]`.
  - Permanent dual-tool entries: `probe_program` and `probe_flash`
    both resolve to `BrokerCore.program(...)`.
  - Error shape from § 4 of the protocol spec: `isError: true` +
    error JSON in `TextContent` on exception.

- **Unix-socket JSON RPC adapter** (`transports/socket.py`):
  - `socketserver.ThreadingUnixStreamServer` on
    `BrokerConfig.socket_path`.
  - Creates parent directory if missing; sets `SO_REUSEADDR`.
  - Wire shape: line-delimited JSON; request
    `{"method": "<name>", "kwargs": {...}}`; permanent `"flash"` →
    `"program"` verb alias; response is serialised result model or
    error object (§ 4).
  - Authn: `SO_PEERCRED` UID match against the process owner.

- **Loopback TCP JSON RPC adapter** (`transports/tcp.py`):
  - `socketserver.ThreadingTCPServer` bound to
    `BrokerConfig.tcp_host:tcp_port`.
  - Refuses to start if `tcp` in `PROBE_BROKER_TRANSPORTS` and no
    token configured (R1 mitigation).
  - Bearer token authn: first line of each connection is the token;
    mismatch → close.
  - Same wire shape and verb-alias policy as socket adapter.

- **Concurrent binding** (`__main__.py` or `serve.py`):
  - At process start, reads `BrokerConfig.transports`.
  - Instantiates one `BrokerCore`.
  - Spawns one `threading.Thread` per enabled adapter; all share
    the same `BrokerCore` reference.
  - Adapter threads are daemon threads; main thread joins on
    `KeyboardInterrupt` / `SIGTERM`.

- **Launcher** (`launcher.py` or `cli.py` extension):
  - `flock` on `$XDG_RUNTIME_DIR/brontes-probe-mcp.lock` (fallback
    `/tmp/brontes-probe-mcp.lock`).
  - Try-connect to socket or TCP (whichever is in `TRANSPORTS`).
  - If connect succeeds → exit critical section; print existing
    socket path for callers.
  - If connect fails → `docker run -d --name brontes-probe-mcp …`
    (named-container singleton; second concurrent spawn hits "name
    in use" and fails cleanly).
  - PID-file fallback at `$XDG_RUNTIME_DIR/brontes-probe-mcp.pid`
    for native (no-Docker) invocation.

- **Tri-transport parity test** (`tests/test_transport_parity.py`):
  - Spins up a real `BrokerCore` (with mocked subprocess layer) and
    all three adapters in-process.
  - Issues each of the 14 tool calls via each transport.
  - Asserts identical result-model JSON across all three paths.
  - Risk R1 mitigation evidence.

- **`brontes-probe-mcp-cli` updates** (`cli.py`):
  - `--transports` flag wired through to `BrokerConfig`.
  - `serve` sub-command that starts the concurrent multi-transport
    server.

- **Evidence:** `artifacts/validation/phase-1/chunk-1.2/run_<UTC>/`

### Out of scope

- Dockerfile / docker-compose / cosign — chunk 1.3.
- Real Docker launch in tests (mocked) — parity test uses in-process
  adapters only.
- High-availability / failover — out of phase.

## Key Design Decisions

1. **Thread-per-adapter, not async.** Matches cockpit's proven
   `ThreadingUnixStreamServer` substrate. stdio adapter is async
   (MCP SDK requirement); runs in its own thread via `asyncio.run`.

2. **Single `BrokerCore` lock.** `BrokerCore` inherits the
   `threading.RLock` from the cockpit `ProbeBroker` pattern; all
   adapter threads share it. No additional lock layer.

3. **Verb alias in dispatch table.** Both `"flash"` and `"program"`
   are registered at the transport layer; both resolve to
   `BrokerCore.program`. No deprecation.

4. **TCP token mandatory.** If `tcp` in `PROBE_BROKER_TRANSPORTS`
   and neither `PROBE_BROKER_TOKEN` nor `PROBE_BROKER_TOKEN_FILE` is
   set, the adapter raises `RuntimeError` at startup (not at first
   connection). Fail-loud.

5. **`socketserver` over asyncio for socket/TCP.** Simpler threading
   model; each connection gets its own thread from the server's pool.
   Sufficient for the single-probe, low-concurrency use case.

## Acceptance Criteria

| ID | Criterion |
|---|---|
| `SCN-1.2-ADAPTERS` | All three `transports/` modules have callable `run(broker)` functions (no `NotImplementedError`). |
| `SCN-1.2-PARITY` | `test_transport_parity.py` passes — all 14 calls via all 3 transports return identical result JSON. |
| `SCN-1.2-TCP-REJECT` | `test_transport_tcp.py::test_no_token_raises` confirms TCP adapter refuses to start without token. |
| `SCN-1.2-VERB-ALIAS` | Parity test confirms `probe_flash` and `probe_program` both resolve to `BrokerCore.program`. |
| `SCN-1.2-CI` | All 4 CI matrix cells green. |
| `SCN-1.2-MYPY` | `mypy --strict src/` exits 0. |
| `SCN-1.2-BOARD` | Board review completed before merge; review record in evidence dir. |

## Risks Activated

- **R1 (tri-transport concurrency defect)** — primary. Mitigated by
  parity test suite. Board review required at this chunk.

## File Map

New:
- `tests/test_transport_parity.py`
- `tests/test_transport_socket.py`
- `tests/test_transport_tcp.py`
- `tests/test_transport_stdio.py`
- `src/brontes_probe_mcp/launcher.py`
- `artifacts/validation/phase-1/chunk-1.2/run_<UTC>/chunk_1_2_record.md`
- `artifacts/validation/phase-1/chunk-1.2/run_<UTC>/board_review.md`

Modified:
- `src/brontes_probe_mcp/transports/stdio.py` — full MCP implementation
- `src/brontes_probe_mcp/transports/socket.py` — full socket implementation
- `src/brontes_probe_mcp/transports/tcp.py` — full TCP implementation
- `src/brontes_probe_mcp/__main__.py` — concurrent multi-transport server
- `src/brontes_probe_mcp/cli.py` — `serve` sub-command; `--transports`

## Rollback

`git revert` the chunk-1.2 squash-merge. Adapters revert to stubs;
no container image exists yet; no external release.

## Open Questions

*(None at plan time.)*
