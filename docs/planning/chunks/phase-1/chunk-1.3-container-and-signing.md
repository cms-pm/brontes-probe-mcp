# Chunk 1.3 — Container + Signing

**Status:** Planned
**Depends on:** 1.2 closed; three transports parity-proven.
**Risk tier:** Medium

## Purpose

Author a production-grade multi-stage `Dockerfile` with a digest-pinned
base image and baked `org.opencontainers.image.revision` label. Add the
GHCR multi-arch CI build (`linux/amd64` + `linux/arm64`) with cosign
OIDC keyless signing. Draft the Docker MCP Catalog submission manifest.
Capture the Docker MCP Catalog submission-rules snapshot (risk R3
mitigation — deferred from 1.0).

## Scope

### In scope

- **`Dockerfile`** (multi-stage, production):
  - Stage 1 `builder`: `FROM python:<version>-slim@sha256:<digest>`.
    Digest-pinned FROM (risk R5 mitigation).
  - Stage 2 `runtime`: copies built wheel; installs runtime deps
    including `pyocd` (pinned); sets `ENTRYPOINT` to
    `python -m brontes_probe_mcp`.
  - `LABEL org.opencontainers.image.revision` baked from
    `DOCKER_BUILD_REVISION` build-arg (wired in CI via
    `${{ github.sha }}`).
  - `LABEL org.opencontainers.image.source` and `.licenses` per OCI
    image spec.
  - `PROBE_BROKER_IMAGE_DIGEST` env var surfaced via CI build arg —
    the running image populates this from `docker inspect` at start.

- **`docker-compose.yml`** (Option C from protocol spec § 10.6):
  - `container_name: brontes-probe-mcp`.
  - Bind-mount `$HOME/.brontes-probe-mcp:/run/brontes-probe-mcp`.
  - `restart: unless-stopped`.
  - Healthcheck: `brontes-probe-mcp-cli session-status`.
  - USB device passthrough: `/dev/bus/usb`.

- **CI — GHCR multi-arch build** (`.github/workflows/release.yml` or
  new job in `ci.yml`):
  - `docker buildx build --platform linux/amd64,linux/arm64`.
  - Push to `ghcr.io/cms-pm/brontes-probe-mcp` on `main` push and
    tags.
  - Triggered separately from the matrix test job (does not run on
    every PR; runs on merge to `main` and on version tags).

- **cosign OIDC keyless signing**:
  - `cosign sign --yes --identity-token …` using GitHub Actions OIDC
    token → Fulcio ephemeral cert → Rekor transparency log.
  - No key custody, no rotation (ratified in 1.0 ratified decisions).
  - Signs the manifest digest pushed to GHCR.

- **Docker MCP Catalog submission manifest draft**:
  - `docs/catalog/docker-mcp-catalog-manifest.yaml` (draft, not
    submitted until 1.4).
  - Fills out fields required by the Catalog submission process per
    the rules snapshot captured in this chunk's evidence.

- **Submission-rules snapshot** (deferred from 1.0, risk R3):
  - `artifacts/validation/phase-1/chunk-1.3/run_<UTC>/docker_mcp_catalog_rules_snapshot.md`
  - Captures the current Docker MCP Catalog submission requirements
    before authoring the manifest so the manifest is grounded.

- **README updates**:
  - Add `## Quick start` with Option A (socket) and Option B (TCP)
    `docker run` snippets.
  - Add Option C `docker compose up -d` snippet.
  - Image coordinates (`ghcr.io/cms-pm/brontes-probe-mcp`), digest
    pinning policy.

- **Evidence:** `artifacts/validation/phase-1/chunk-1.3/run_<UTC>/`

### Out of scope

- Actual Docker MCP Catalog submission (chunk 1.4).
- Anthropic MCP registry submission (chunk 1.4).
- Cockpit-side submodule / facade (Phase 2).

## Key Design Decisions

1. **Digest-pinned `FROM`.** The base image SHA256 is pinned in the
   Dockerfile. CI regenerates the Dockerfile comment showing the tag
   each release; the digest is the authoritative anchor.

2. **`linux/amd64` + `linux/arm64` only.** `linux/arm/v7` deferred;
   not a primary embedded dev host target.

3. **OIDC keyless cosign** (ratified 1.0). No private key material
   in the repo or GitHub secrets. Ephemeral cert per release. Fulcio
   + Rekor are the trust roots.

4. **Release job gates on test matrix.** The GHCR build and sign job
   depends on the 4-cell test matrix completing green. No image ships
   from a failing commit.

## Acceptance Criteria

| ID | Criterion |
|---|---|
| `SCN-1.3-DOCKERFILE` | `docker build .` succeeds locally; `ENTRYPOINT` resolves to `python -m brontes_probe_mcp`. |
| `SCN-1.3-LABEL` | `docker inspect` output contains `org.opencontainers.image.revision` label. |
| `SCN-1.3-MULTIARCH` | CI build produces a manifest list with `linux/amd64` + `linux/arm64` entries. |
| `SCN-1.3-COSIGN` | `cosign verify --certificate-identity-regexp … ghcr.io/cms-pm/brontes-probe-mcp@sha256:…` exits 0 post-push. |
| `SCN-1.3-CATALOG-DRAFT` | `docs/catalog/docker-mcp-catalog-manifest.yaml` present and complete per rules snapshot. |
| `SCN-1.3-RULES-SNAPSHOT` | Evidence dir contains `docker_mcp_catalog_rules_snapshot.md`. |
| `SCN-1.3-COMPOSE` | `docker compose config` validates `docker-compose.yml` without error. |
| `SCN-1.3-README` | `README.md` contains `docker run` snippets for both Option A and Option B. |

## Risks Activated

- **R3 (Docker MCP Catalog criteria opaque)** — mitigated by
  capturing the rules snapshot before authoring the manifest.
- **R5 (build reproducibility)** — accepted; image freezes pulled
  bytes per release. Honest caveat documented in README and CHANGELOG.

## File Map

New:
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore` (update existing placeholder)
- `docs/catalog/docker-mcp-catalog-manifest.yaml`
- `.github/workflows/release.yml`
- `artifacts/validation/phase-1/chunk-1.3/run_<UTC>/chunk_1_3_record.md`
- `artifacts/validation/phase-1/chunk-1.3/run_<UTC>/docker_mcp_catalog_rules_snapshot.md`

Modified:
- `README.md` — Quick start, Option A/B/C snippets, image coordinates
- `CHANGELOG.md` — 0.1.0-dev section started

## Rollback

`git revert` chunk-1.3 squash-merge. Dockerfile removed; GHCR image
may already be pushed (cannot un-push, but the tag can be deleted
from GHCR). cosign transparency log entries are permanent (Rekor);
document in CHANGELOG that the pre-release signature was experimental.

## Open Questions

*(Anthropic MCP registry submission-rules snapshot — captured in
chunk 1.4 immediately before submission, per risk R4.)*
