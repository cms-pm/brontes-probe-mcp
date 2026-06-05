# Chunk 1.2 Validation Record

**Date:** 2026-06-04
**Run ID:** run_20260604T000000Z

## Scope

Transport adapters + launcher for `brontes-probe-mcp`:
- `transports/_rpc.py` — shared dispatch/serialization (verb alias, Path coercion, `recent_lines` wrapper)
- `transports/socket.py` — Unix-domain socket JSON-RPC adapter (ThreadingUnixStreamServer)
- `transports/tcp.py` — loopback TCP JSON-RPC adapter with bearer-token auth (ThreadingTCPServer)
- `transports/stdio.py` — MCP stdio adapter (15 tools incl. `probe_flash` alias)
- `__main__.py` — concurrent multi-transport launcher (`serve_all`)
- `cli.py` — `serve` subcommand added
- `launcher.py` — singleton flock-based Docker launcher

## SCN Criteria

| ID | Criterion | Status |
|----|-----------|--------|
| SCN-1.2-SOCK-RPC | Unix-socket adapter accepts JSON-line requests, dispatches to BrokerCore, returns JSON-line responses | Pending (CI not yet run) |
| SCN-1.2-TCP-RPC | TCP adapter enforces bearer-token auth, dispatches identically to socket adapter | Pending (CI not yet run) |
| SCN-1.2-STDIO-MCP | stdio adapter exposes 15 MCP tools (14 unique + probe_flash alias), calls BrokerCore | Pending (CI not yet run) |
| SCN-1.2-VERB-ALIAS | `flash`→`program` alias in socket/TCP; `probe_flash`→`probe_program` in stdio; both return identical JSON | Pending (CI not yet run) |
| SCN-1.2-RECENT-LINES | `recent_lines` response wrapped as `{"lines": [...], "next_seq": N}` on all three transports | Pending (CI not yet run) |
| SCN-1.2-TCP-TOKEN | TCP transport raises RuntimeError at startup if no bearer token configured | Pending (CI not yet run) |
| SCN-1.2-SOCK-PEERCRED | SO_PEERCRED UID check on socket with graceful fallback on macOS | Pending (CI not yet run) |
| SCN-1.2-PARITY | All 16 tool/method calls produce identical JSON across all three transports | Pending (CI not yet run) |
| SCN-1.2-LAUNCHER | Singleton launcher flock-checks existing server before spawning Docker | Pending (CI not yet run) |
| SCN-1.2-MULTI-TRANSPORT | serve_all starts socket/tcp/stdio as concurrent daemon threads over one BrokerCore | Pending (CI not yet run) |

## Local Verification (2026-06-04)

- **mypy --strict src/:** PASS — no issues in 15 source files
- **ruff check src/ tests/:** PASS — all checks passed
- **pytest -q -m "not hardware":** PASS — 111 passed, 3 deselected (hardware)

## Board Review

Pending

## Notes

- `duration_s` and `snapshot_at` are timing-sensitive fields excluded from parity comparison in `test_parity_path_args` (structural equivalence verified for all other fields)
- macOS AF_UNIX path limit (104 chars) addressed: socket tests use `tempfile.TemporaryDirectory(dir="/tmp")`
- macOS `ConnectionResetError` on wrong-token TCP close handled in test assertion
- SO_PEERCRED macOS fallback: `getattr(socket, "SO_PEERCRED", None)` guards Linux-only syscall
