# Phase 1 TODO — Bootstrap to First Release

## Focus

Phase 1 establishes `brontes-probe-mcp` as a fully operational, independently
distributable MCP server for embedded debug-probe orchestration. It moves from
the typed-skeleton bootstrap (1.0) through real pyocd-backed implementation,
three concurrent transport adapters, a reproducible multi-arch container, and
the first signed public release.

No in-tree caller migration is in scope for Phase 1. The surface stabilises
here; consumers wire against it in Phase 2.

## Gate Posture

- **Board review:** chunk 1.2 (transport parity — tri-transport concurrency is
  the highest blast-radius change before release); chunk 1.4 (release
  governance).
- **Release governance:** chunk 1.4 triggers the release gate. A signed GHCR
  image reachable at the pinned digest is the ship condition.
- **No chunk opens** until the previous chunk's closeout commit lands on `main`.

## Roadmap At A Glance

- **1.0** ✓ — Repo skeleton: `pyproject.toml`, typed `BrokerCore` surface,
  `BrokerConfig(BaseSettings)`, transport / session / lane stubs,
  40-test smoke suite, 2×2 CI matrix, Jinja client config templates,
  governance files (README, CHANGELOG, COC, CONTRIBUTING).
- **1.1** — Core implementation: `SessionManager` + `LaneSupervisor` real
  pyocd calls; all 15 `BrokerCore` method bodies; full regression suite
  replacing the `NotImplementedError` stubs.
- **1.2** — Transport adapters + launcher: `stdio`, `socket`, `tcp` adapter
  implementations; flock + try-connect + named-container singleton launcher;
  tri-transport parity test. **Board-review trigger.**
- **1.3** — Container + signing: multi-stage `Dockerfile` (digest-pinned
  `FROM`, baked `org.opencontainers.image.revision`); GHCR multi-arch build
  (`linux/amd64` + `linux/arm64`); cosign OIDC keyless signing; Docker MCP
  Catalog submission manifest draft.
- **1.4** — First release: `0.1.0` version bump; GHCR signed image; Docker
  MCP Catalog submission (primary); Anthropic MCP registry submission;
  `CHANGELOG.md` `0.1.0` section complete. **Release governance trigger.**

## Practical Sequence

| Priority | Chunk | Status | Risk Tier | Depends On |
| --- | --- | --- | --- | --- |
| 1 | `1.0` | **Closed** (`ed0e5fb` on `main`, 2026-06-04) | Low | — |
| 2 | `1.1` | Planned | Medium | 1.0 closed; CI green on skeleton. |
| 3 | `1.2` | Planned | High | 1.1 closed; full pyocd test suite green. |
| 4 | `1.3` | Planned | Medium | 1.2 closed; three transports parity-proven. |
| 5 | `1.4` | Planned | Medium | 1.3 closed; signed image reachable on GHCR; CHANGELOG drafted. |

## Hard Prereqs

- **pyocd hardware availability:** chunk 1.1 requires a physical SWD target for
  integration tests. CI matrix uses mocked pyocd for unit coverage; hardware
  tests are gated behind `pytest -m hardware` and excluded from CI by default.
- **GHCR write access:** chunk 1.3 requires `GHCR_TOKEN` secret in repo
  Actions settings.
- **Docker MCP Catalog submission rules snapshot:** captured in chunk 1.3
  evidence dir before authoring the submission manifest. Risk R3.
- **Anthropic MCP registry rules snapshot:** captured before authoring the
  registry submission in chunk 1.4. Risk R4.

## Pool Question Index

*(No open pool questions at phase open. Add YAML files here as questions arise.)*

## Ratified Decisions (carried from 1.0)

| Decision | Choice |
|---|---|
| Python floor | `>=3.11` |
| `mcp` SDK | Main runtime dep; no `[mcp]` extra |
| Signing posture | OIDC keyless cosign — GitHub Actions OIDC → Fulcio → ephemeral cert → Rekor transparency log. No key custody. |
| Transport defaults | `stdio,socket` (`PROBE_BROKER_TRANSPORTS`) |
| Lane defaults | `swd,itm_swo` (`PROBE_BROKER_LANES`) |
| Distribution primary | Docker MCP Catalog; GHCR (`ghcr.io/cms-pm/brontes-probe-mcp`) registry of record |
| PyPI wheel | Namespace reserved at 0.0.0; functional wheel deferred past Phase 1 |
| CI matrix | `{ubuntu-22.04, macos-14} × {3.11, 3.12}` |
| Mypy | `strict = true` from day one |
