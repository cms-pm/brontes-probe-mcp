# Phase 1 Risk Register — brontes-probe-mcp

| ID | Title | Tier | Status | Mitigation |
|---|---|---|---|---|
| R1 | Tri-transport concurrency defect | High | Open (1.2) | Parity test suite across all three transports; board review at 1.2. |
| R2 | pyocd API surface instability | Medium | Open (1.1) | Pin `pyocd` to a tested minor version in `pyproject.toml`; CI locks the version. |
| R3 | Docker MCP Catalog curation criteria opaque | Medium | Open (1.3) | Capture submission-rules snapshot in 1.3 evidence dir before authoring the manifest. |
| R4 | Anthropic MCP registry rules change | Low | Open (1.4) | Capture registry rules snapshot before submission in 1.4. |
| R5 | Build reproducibility (pulled bytes, not source) | Low | Accepted | Image freezes the pulled bytes per release. SBOM captures exact layer digests. Documented in CHANGELOG. |
| R6 | GHCR availability SLA | Low | Accepted | Sigstore-signed manifests + offline-load procedure documented in `docs/ops/`. No registry mirror (cost not justified). |
| R7 | PyPI name squatting | Low | Closed | `brontes-probe-mcp` 0.0.0 placeholder reserved. Functional wheel deferred. |
| R8 | Per-AI-client config drift | Low | Closed | Jinja2 templates + `render_client_configs.py --check` in CI (1.0). |
| R9 | Hardware-in-the-loop CI flakiness | Medium | Open (1.1) | Hardware tests isolated behind `pytest -m hardware`; excluded from matrix CI; run manually pre-release. |
