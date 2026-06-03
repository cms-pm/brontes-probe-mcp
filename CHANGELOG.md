# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
