# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

*(no changes yet)*

## [0.2.2] - 2026-06-10

### Fixed

- README relative links (CHANGELOG, LICENSE, docs/tutorials) replaced with
  absolute GitHub URLs so they resolve correctly on PyPI.

## [0.2.1] - 2026-06-10

Image digest (pinned):
`ghcr.io/cms-pm/brontes-probe-mcp@sha256:61e4d0423085ac734a938b2a45a984e5197e1803326547f5d13d519e67798e91`

### Fixed

- `__version__` in `brontes_probe_mcp.__init__` was not updated to match
  `pyproject.toml` in the `0.2.0` release, causing a mismatch between
  `importlib.metadata.version()` and the module attribute.

### Changed

- README restructured: Quick start is now the first major section; deployment
  options lead with probe/target auto-detection; all client config snippets
  include the packs volume mount (`/packs`) and `CMSIS_PACK_ROOT` env var
  that were missing in `0.2.0`.

## [0.2.0] - 2026-06-09

### Added

**pip install deployment path**

- `pip install brontes-probe-mcp` installs a fully functional native server;
  no Docker required. Entry point: `brontes-probe-mcp-cli serve`.
- `brontes-probe-mcp-cli probe-agent` subcommand manages the host-side pyocd
  gdbserver daemon: `start`, `stop`, `status`.
  - `probe-agent start` auto-detects probe and target when exactly one probe
    is connected with a deterministic target; `--target`, `--probe-uid`,
    `--port`, `--frequency-hz`, `--pack` allow fine-grained control.
  - State written to `~/.brontes-probe-mcp/agent.json`; persists across MCP
    server restarts.
- `PROBE_BROKER_AGENT_STATE_DIR` config variable (default `~/.brontes-probe-mcp`)
  — controls where `probe-agent start` writes its state and where
  `session_start` looks for a running agent.

**Transparent probe-agent auto-discovery in `session_start`**

- If `~/.brontes-probe-mcp/agent.json` exists and the recorded GDB port is
  reachable, `session_start` connects to the running agent instead of
  spawning a new pyocd process — even on loopback. Fully backwards-compatible:
  no state file → original spawn-on-demand behavior.
- Enables the macOS / Docker Desktop split: host runs `probe-agent`, container
  connects via volume-mounted state file without `--device` pass-through.

**PyPI automated publishing**

- `.github/workflows/publish.yml` — builds wheel + sdist and publishes to
  PyPI on `v*` tags via OIDC trusted publishing (no stored credentials).
  Runs independently of `release.yml` so each can be retried.

### Changed

- `PROBE_BROKER_SOCKET_PATH` default changed from `/run/brontes-probe-mcp/probe.sock`
  (Docker-centric) to `~/.brontes-probe-mcp/probe.sock`. Dockerfile sets the
  env var explicitly so container behavior is unchanged.
- `pyocd` version constraint relaxed from `>=0.36,<0.37` to `>=0.36`, allowing
  pip install users to use newer pyocd releases.
- `SessionManager.start/stop/status` accept a `profile` keyword so the
  probe-agent CLI writes to `agent.json` while the MCP server uses `default.json`.

## [0.1.0] - 2026-06-04

First operational release. The typed skeleton from `0.0.0` is replaced by a
fully callable `BrokerCore` backed by real `SessionManager`, `LaneSupervisor`,
and three concurrent transport adapters. Distribution is via the signed
multi-arch GHCR image; PyPI wheel is reserved at `0.0.0` and deferred.

Image digest (pinned): see `artifacts/validation/phase-1/chunk-1.4/` once CI
completes for `v0.1.0`.

### Added

**Core broker (`core/`)**

- `SessionManager` — full pyocd/openocd gdbserver subprocess supervisor:
  `start`, `stop`, `status`. Single-session semantics (implicit replace on
  `start`). Operation lock via `O_CREAT|O_EXCL` with stale-lock auto-recovery
  (60 s threshold). `os.killpg` process-group termination with SIGTERM → poll
  → SIGKILL fallback. Session metadata persisted as `default.json`.
- `LaneSupervisor` + `ItmSwoLane` — real lane state management with
  `threading.Lock` on all mutations; snapshot-before-iterate in `lane_status`.
- `BrokerCore` — all 15 method bodies callable:
  - `session_start` / `session_stop` / `session_status`
  - `halt`, `resume`, `reset` (soft/hard)
  - `program` (elf/bin/hex) — GDB `monitor halt` + `load`; parses
    `load size N` from GDB stdout for `programmed_bytes`.
  - `mem_read` — GDB `x/<n>wx`; returns base64 bytes (default) or hex word
    list; little-endian word order.
  - `blackbox_export` — GDB `dump binary memory`; default range
    `0x08000000`–`0x08080000` (512 KB). Requires active session.
  - `itm_stream_start` / `itm_stream_stop`
  - `lane_status` / `lane_release` / `lane_resume`
  - `recent_lines` — filtered slice of the 256-entry audit `deque`.
- `MemReadResult.value` typed `str | list[str]` for format-polymorphic
  responses.

**Transport adapters (`transports/`)**

- `_rpc.py` — shared JSON-RPC dispatch: verb aliases (`flash`→`program`,
  `probe_flash`→`probe_program`), `Path` coercion, `recent_lines` wrapper
  (`{"lines": [...], "next_seq": N}`).
- `socket.py` — `ThreadingUnixStreamServer` JSON-line adapter with
  `SO_PEERCRED` UID check (macOS graceful fallback).
- `tcp.py` — `ThreadingTCPServer` JSON-line adapter with bearer-token auth;
  `PROBE_BROKER_TCP_ALLOW_REMOTE=true` required for non-loopback binding.
- `stdio.py` — MCP stdio adapter; exposes 15 tools (14 unique +
  `probe_flash` alias) via the `mcp` SDK.
- `__main__.py` — `serve_all()` launches socket, TCP, and stdio as concurrent
  daemon threads over a single `BrokerCore` instance.
- `launcher.py` — singleton flock-based Docker launcher: flock-checks for
  existing server before spawning a new container.

**CLI (`cli.py`)**

- `serve` subcommand with `--transports <csv>`.
- `session-unlock` subcommand for manual stale-lock recovery.
- Top-level `--transports` flag removed (COM-010).

**Container + CI/CD**

- Multi-stage `Dockerfile` — `builder` stage builds the wheel; `runtime`
  stage installs from wheel + `libusb`. Base image pinned by digest (R5).
- `docker-compose.yml` — Option C bind-mount socket deployment.
- `.github/workflows/release.yml` — GHCR multi-arch build (`linux/amd64` +
  `linux/arm64`) gated on 2×2 test matrix; cosign OIDC keyless signing
  (Fulcio + Rekor, no key custody).

**Documentation**

- `docs/catalog/docker-mcp-catalog-manifest.yaml` — Docker MCP Catalog
  submission manifest.
- `docs/tutorials/blackbox-export.md` — tutorial for `probe_blackbox_export`.
- README Quick start (Options A/B/C) and `probe_blackbox_export` section.

**Reliability (board review COM-003 – COM-010)**

- `mem_read` default format corrected to `"bytes"` (COM-003).
- `LaneSupervisor` + `ItmSwoLane` thread-safety (COM-004).
- `os.killpg` process-group termination (COM-005).
- Stale operation-lock auto-recovery + `session-unlock` CLI (COM-006).
- `blackbox_export` implemented (COM-007).
- Client config templates: `--name` flag removed to prevent TSR daemon
  name collision (COM-008b). `tcp_allow_remote` loopback enforcement
  in `serve_all` (COM-008c).
- Single-session implicit replace on `session_start` (COM-009).
- Top-level `--transports` CLI flag removed; moved to `serve` subcommand
  (COM-010).

### Fixed

- GDB error propagation: non-zero exit code raises `RuntimeError` with
  stderr detail (FND-001).
- `_require_session` guard on all probe operations (FND-002).

### Notes on build reproducibility (R5)

The Dockerfile pins the Python base image by digest. To refresh the pin:
`docker pull python:3.12-slim && docker inspect --format '{{index .RepoDigests 0}}'`.

## [0.0.0] - 2026-05-01

PyPI namespace reservation (`Development Status :: 1 - Planning`). No
functional wheel. Typed `BrokerCore` surface and repo skeleton
(`pyproject.toml`, CI matrix, governance files).

[Unreleased]: https://github.com/cms-pm/brontes-probe-mcp/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/cms-pm/brontes-probe-mcp/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/cms-pm/brontes-probe-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/cms-pm/brontes-probe-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cms-pm/brontes-probe-mcp/releases/tag/v0.1.0
[0.0.0]: https://github.com/cms-pm/brontes-probe-mcp/releases/tag/v0.0.0
