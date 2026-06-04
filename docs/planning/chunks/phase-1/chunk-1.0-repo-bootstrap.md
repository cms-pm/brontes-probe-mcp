# Chunk 1.0 — Repo Bootstrap

**Status:** Closed (`ed0e5fb` on `main`, 2026-06-04T09:27:53Z)
**Branch:** `bootstrap/skeleton-and-ci` → squash-merged via PR #1

## Scope

Establish the repo skeleton, typed public surface, CI matrix, and client
config anti-drift tooling. No operational code; no probe calls. Every
subsequent chunk builds on this surface.

## What Landed

| Area | Detail |
|---|---|
| `pyproject.toml` | PEP 621, setuptools src-layout, `requires-python>=3.11`, runtime: `pydantic>=2.6`, `pydantic-settings>=2.2`, `mcp>=1.0`. `[dev]` extra. Console script `brontes-probe-mcp-cli`. `mypy strict=true`. |
| `src/brontes_probe_mcp/core/config.py` | `BrokerConfig(BaseSettings, env_prefix="PROBE_BROKER_")` — **functional**. Custom `_CsvEnvSource` handles CSV parsing for `list[str]` fields (`transports`, `lanes`). |
| `src/brontes_probe_mcp/core/broker.py` | 15 typed `BrokerCore` methods (signatures match protocol spec exactly); all raise `NotImplementedError("1.1 implementation")`. |
| `src/brontes_probe_mcp/core/models.py` | Pydantic result models: `ProgramResult`, `ProbeState`, `MemReadResult`, `BlackboxExportResult`, `ItmStreamHandle`, `ItmStreamSummary`, `LaneStatus`, `LogLine`, `SessionStatus`. |
| `src/brontes_probe_mcp/core/session.py` | `SessionManager` stub — all raise `NotImplementedError("1.1 implementation")`. |
| `src/brontes_probe_mcp/core/lanes.py` | `ItmSwoLane` + `LaneSupervisor` stubs — all raise `NotImplementedError("1.1 implementation")`. |
| `src/brontes_probe_mcp/transports/` | `stdio`, `socket`, `tcp` — each has `run(broker: BrokerCore) -> None` raising `NotImplementedError("1.2 implementation")`. |
| `src/brontes_probe_mcp/cli.py` | `main()` with `--version`, `--config-dump` (functional), `--transports <csv>` (stub). |
| `tests/` | 40 tests: import surface, `NotImplementedError` surface, config env-var (CSV + defaults), CLI smoke. |
| `.github/workflows/ci.yml` | Matrix `{ubuntu-22.04, macos-14} × {3.11, 3.12}`; steps: ruff, mypy, pytest, build, render-check. |
| `docs/clients/*.json.j2` | Jinja2 templates for Claude Desktop, Claude Code, Codex, OpenCode. |
| `scripts/render_client_configs.py` | Renders templates into README between named markers; `--check` mode in CI. |
| `README.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `.dockerignore` | Governance and documentation scaffolding. |
| `.governance/ai-dev-governance` | ADG v1.1.5 submodule pinned at `cc1eccc`. |

## CI Evidence

- Run: https://github.com/cms-pm/brontes-probe-mcp/actions/runs/26943216499
- Matrix: 4/4 green (ubuntu-22.04 + macos-14 × 3.11 + 3.12)
- Evidence dir: `artifacts/validation/phase-1/chunk-1.0/run_20260604T181228Z/`

## Technical Note

`pydantic-settings` v2 calls `json.loads()` on `list[str]` field env vars
before Pydantic validators fire. `field_validator(mode="before")` is too late.
Fix: subclass `EnvSettingsSource`, override `prepare_field_value`, wire via
`settings_customise_sources`. See `core/config.py`.
