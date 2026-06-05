# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Multi-stage production `Dockerfile` — `builder` stage builds the wheel;
  `runtime` stage installs from wheel + `libusb`. Base image pinned to
  `python:3.12-slim@sha256:090ba77e…` (R5 mitigation: reproducibility via
  digest lock, honest caveat documented here).
- `docker-compose.yml` — Option C bind-mount socket deployment
  (`container_name: brontes-probe-mcp`, `restart: unless-stopped`,
  healthcheck via `brontes-probe-mcp-cli session-status`, USB device
  passthrough).
- `.github/workflows/release.yml` — GHCR multi-arch build (`linux/amd64` +
  `linux/arm64`) gated on the full 2×2 test matrix; cosign OIDC keyless
  signing (Fulcio + Rekor, no key custody). Triggers on push to `main` and
  version tags.
- `docs/catalog/docker-mcp-catalog-manifest.yaml` — Docker MCP Catalog
  submission manifest draft (submission gated on 1.4).
- Docker MCP Catalog submission-rules snapshot captured in
  `artifacts/validation/phase-1/chunk-1.3/run_20260604T000000Z/` (R3
  mitigation).
- README Quick start section with Option A (socket), Option B (TCP), and
  Option C (Compose) `docker run`/`docker compose` snippets.

### Note on build reproducibility (R5)

The Dockerfile pins the Python base image by digest. The digest captures the
exact layer bytes pulled at build time. A future `docker pull python:3.12-slim`
may return different bytes under the same tag. To refresh the pin:
`docker pull python:3.12-slim && docker inspect --format '{{index .RepoDigests 0}}'`.

---

## Pre-0.1.0 development history

### Added

- `pyproject.toml` — PEP 621 metadata, setuptools src-layout backend,
  `requires-python = ">=3.11"`, runtime deps (`pydantic>=2.6`,
  `pydantic-settings>=2.2`, `mcp>=1.0`), `[dev]` extra, console script
  `brontes-probe-mcp-cli`. Strict mypy from day one.
- `src/brontes_probe_mcp/` skeleton with typed `BrokerCore` surface matching
  the v2 protocol specification exactly. All methods raise
  `NotImplementedError` pending implementation; signatures are the stable
  contract for downstream chunks.
- `BrokerConfig(BaseSettings)` with `env_prefix="PROBE_BROKER_"` —
  functional configuration layer; every `PROBE_BROKER_*` env var from the
  protocol spec is a typed Pydantic field with spec-correct defaults.
  `PROBE_BROKER_TRANSPORTS` and `PROBE_BROKER_LANES` parse comma-separated
  input into `list[str]`.
- Transport adapter stubs — `transports/{stdio,socket,tcp}.py` each expose
  `run(broker: BrokerCore) -> None` raising `NotImplementedError`, holding
  the interface for the 8.7.2c implementation.
- Session and lane stubs — `core/session.py` (`SessionManager`) and
  `core/lanes.py` (`LaneSupervisor`, `ItmSwoLane`).
- `cli.py` — `brontes-probe-mcp-cli` entry with `--version`, `--config-dump`
  (JSON), and `--transports <csv>` parsing.
- Smoke test suite — import test, `NotImplementedError` surface test (pins
  all 15 typed `BrokerCore` method signatures), config env-var test, CLI
  smoke test.
- CI matrix — `{ubuntu-22.04, macos-13}` × `{3.11, 3.12}`, jobs: `ruff
  check`, `mypy --strict`, `pytest`, `python -m build`, render config check.
- `docs/clients/{claude_desktop,claude_code,codex,opencode}.json.j2` — Jinja
  templates for the four AI-client MCP configuration snippets (single source,
  R13 anti-drift).
- `scripts/render_client_configs.py` — renders templates into README's
  `<!-- BEGIN/END client-configs -->` markers; CI runs in `--check` mode.
- `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1).
- `CONTRIBUTING.md` — dev setup and PR review guidance.
- `.dockerignore` — authored ahead of the real multi-stage `Dockerfile`
  (deferred to next release cycle).
