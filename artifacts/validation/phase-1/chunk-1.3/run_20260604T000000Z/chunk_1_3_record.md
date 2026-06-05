# Chunk 1.3 Validation Record
# Run: 2026-06-04T000000Z

## Acceptance Criteria

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| SCN-1.3-DOCKERFILE | `docker build .` succeeds; ENTRYPOINT resolves to `python -m brontes_probe_mcp` | Pending CI | Dockerfile in repo root; multi-stage builder + runtime |
| SCN-1.3-LABEL | `docker inspect` shows `org.opencontainers.image.revision` | Pending CI | `LABEL org.opencontainers.image.revision="${DOCKER_BUILD_REVISION}"` in Dockerfile |
| SCN-1.3-MULTIARCH | CI produces manifest list with linux/amd64 + linux/arm64 | Pending merge to main | `release.yml` build-and-push step: `platforms: linux/amd64,linux/arm64` |
| SCN-1.3-COSIGN | `cosign verify` exits 0 post-push | Pending merge to main | `release.yml` sign step using OIDC keyless |
| SCN-1.3-CATALOG-DRAFT | `docs/catalog/docker-mcp-catalog-manifest.yaml` present and complete | Done | File authored, all required fields populated |
| SCN-1.3-RULES-SNAPSHOT | Evidence dir contains `docker_mcp_catalog_rules_snapshot.md` | Done | This run dir |
| SCN-1.3-COMPOSE | `docker compose config` validates `docker-compose.yml` | Pending | `docker-compose.yml` authored |
| SCN-1.3-README | README.md contains `docker run` snippets for Option A and Option B | Done | Quick start section added |

## Risks Addressed

- R3 (Docker MCP Catalog criteria opaque) — MITIGATED: rules snapshot captured in this run dir
- R5 (build reproducibility) — ACCEPTED: base image digest pinned in Dockerfile; documented in CHANGELOG

## Files Delivered

New:
- `Dockerfile` — multi-stage, python:3.12-slim@sha256:090ba77... pinned base
- `docker-compose.yml` — Option C (bind-mount socket)
- `.github/workflows/release.yml` — GHCR multi-arch build + cosign signing
- `docs/catalog/docker-mcp-catalog-manifest.yaml` — catalog submission draft
- `artifacts/validation/phase-1/chunk-1.3/run_20260604T000000Z/` — this evidence dir

Modified:
- `.dockerignore` — added `artifacts/` exclusion
- `.github/workflows/ci.yml` — added `container/**` branch pattern
- `README.md` — Quick start section with Option A/B/C snippets
- `CHANGELOG.md` — 0.1.0-dev section with container/signing entries
