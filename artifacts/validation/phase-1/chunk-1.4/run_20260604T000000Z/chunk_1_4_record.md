# Chunk 1.4 Validation Record

**Date:** 2026-06-04
**Run ID:** run_20260604T000000Z

## Scope

First release: version bump to `0.1.0`, GHCR signed multi-arch image,
Docker MCP Catalog submission, Anthropic MCP registry submission,
CHANGELOG `[0.1.0]` section complete.

## SCN Criteria

| ID | Criterion | Status | Notes |
|----|-----------|--------|-------|
| SCN-1.4-VERSION | `import brontes_probe_mcp; print(__version__)` → `0.1.0` | PASS | pyproject.toml + __init__.py bumped |
| SCN-1.4-GHCR | `docker pull ghcr.io/cms-pm/brontes-probe-mcp:0.1.0` succeeds | Pending | Awaiting v0.1.0 tag → release.yml CI |
| SCN-1.4-DIGEST | ghcr_digest.md records sha256 matching docker inspect | Pending | Will be populated post-CI |
| SCN-1.4-COSIGN | `cosign verify` exits 0 | Pending | release.yml keyless sign step |
| SCN-1.4-CATALOG-SUBMITTED | Evidence records Catalog submission URL | Pending | docs/catalog/docker-mcp-catalog-manifest.yaml drafted |
| SCN-1.4-REGISTRY-SUBMITTED | Evidence records Anthropic registry submission URL | Pending | anthropic_mcp_registry_rules_snapshot.md to be captured |
| SCN-1.4-RULES-SNAPSHOT | anthropic_mcp_registry_rules_snapshot.md present | Pending | Capture immediately before submission |
| SCN-1.4-CHANGELOG | CHANGELOG.md has [0.1.0] section | PASS | Full feature summary written |
| SCN-1.4-COMPAT-MATRIX | Protocol spec § 5 compat matrix has 0.1.0 row | Deferred | Protocol spec lives in cockpit sibling repo |
| SCN-1.4-RENDER-CHECK | `render_client_configs.py --check` exits 0 | PASS | image_tag=0.1.0; digest placeholder sha256:TBD until post-CI update |

## Files Delivered

- `pyproject.toml` — version `0.1.0`
- `src/brontes_probe_mcp/__init__.py` — `__version__ = "0.1.0"`
- `CHANGELOG.md` — `[0.1.0]` section complete
- `scripts/render_client_configs.py` — `image_tag` updated to `0.1.0`
- `README.md` — status line updated; client-configs re-rendered

## Pending (post-tag CI)

- `ghcr_digest.md` — populated after `v0.1.0` tag triggers release.yml
- `anthropic_mcp_registry_rules_snapshot.md` — captured before submission
- `catalog_submission.md` — submission confirmation
- `registry_submission.md` — Anthropic registry submission confirmation
- Client config templates — digest `sha256:TBD` updated to real SHA256
- README re-rendered with real digest

## Status: IN PROGRESS
