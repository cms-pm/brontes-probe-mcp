# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

*(no changes yet)*

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

[Unreleased]: https://github.com/cms-pm/brontes-probe-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cms-pm/brontes-probe-mcp/releases/tag/v0.1.0
[0.0.0]: https://github.com/cms-pm/brontes-probe-mcp/releases/tag/v0.0.0
