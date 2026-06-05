# Chunk 1.4 Validation Record

**Date:** 2026-06-04 / 2026-06-05
**Run ID:** run_20260604T000000Z
**Release tag:** v0.1.0
**CI run:** https://github.com/cms-pm/brontes-probe-mcp/actions/runs/27009013966

## Scope

First release: version bump to `0.1.0`, GHCR signed multi-arch image,
Docker MCP Catalog submission, Anthropic MCP registry submission,
CHANGELOG `[0.1.0]` section complete.

## SCN Criteria

| ID | Criterion | Status | Notes |
|----|-----------|--------|-------|
| SCN-1.4-VERSION | `import brontes_probe_mcp; print(__version__)` → `0.1.0` | PASS | pyproject.toml + __init__.py bumped |
| SCN-1.4-GHCR | `docker pull ghcr.io/cms-pm/brontes-probe-mcp:0.1.0` succeeds | PASS | CI run 27009013966; 5/5 green |
| SCN-1.4-DIGEST | ghcr_digest.md records sha256 matching docker inspect | PASS | sha256:77e58b86… — see ghcr_digest.md |
| SCN-1.4-COSIGN | `cosign verify` exits 0 | PASS | release.yml sign step green; OIDC keyless |
| SCN-1.4-CATALOG-SUBMITTED | Evidence records Catalog submission URL | Pending | docs/catalog/docker-mcp-catalog-manifest.yaml ready; submission pending |
| SCN-1.4-REGISTRY-SUBMITTED | Evidence records Anthropic registry submission URL | Pending | anthropic_mcp_registry_rules_snapshot.md to be captured |
| SCN-1.4-RULES-SNAPSHOT | anthropic_mcp_registry_rules_snapshot.md present | Pending | Capture immediately before submission |
| SCN-1.4-CHANGELOG | CHANGELOG.md has [0.1.0] section | PASS | Full feature summary written |
| SCN-1.4-COMPAT-MATRIX | Protocol spec § 5 compat matrix has 0.1.0 row | Deferred | Protocol spec lives in cockpit sibling repo |
| SCN-1.4-RENDER-CHECK | `render_client_configs.py --check` exits 0 | PASS | image_digest and image_tag pinned to 0.1.0 digest |

## Files Delivered

- `pyproject.toml` — version `0.1.0`
- `src/brontes_probe_mcp/__init__.py` — `__version__ = "0.1.0"`
- `CHANGELOG.md` — `[0.1.0]` section complete
- `scripts/render_client_configs.py` — `image_tag=0.1.0`, `image_digest=sha256:77e58b86…`
- `README.md` — status line updated; client-configs re-rendered with pinned digest
- `Dockerfile` — venv pattern; build-essential in builder for arm64 capstone compile
- `artifacts/validation/phase-1/chunk-1.4/run_20260604T000000Z/ghcr_digest.md`

## Pending

- `anthropic_mcp_registry_rules_snapshot.md` — captured before submission
- `catalog_submission.md` — Docker MCP Catalog submission confirmation
- `registry_submission.md` — Anthropic registry submission confirmation

## Status: IN PROGRESS (submissions pending)
