# Chunk 1.4 — First Release

**Status:** Planned
**Depends on:** 1.3 closed; signed GHCR image reachable; CHANGELOG drafted.
**Risk tier:** Medium — release governance trigger.

## Purpose

Ship `brontes-probe-mcp` `0.1.0`: bump the version, push the signed
GHCR image, submit to the Docker MCP Catalog (primary distribution),
and submit to the Anthropic MCP registry (secondary). Populate the
CHANGELOG `0.1.0` section and the protocol-spec compatibility matrix.
Capture the Anthropic MCP registry submission-rules snapshot before
authoring the submission.

## Scope

### In scope

- **Version bump to `0.1.0`**:
  - `pyproject.toml` `[project] version = "0.1.0"`.
  - `src/brontes_probe_mcp/__init__.py` `__version__ = "0.1.0"`.
  - `CHANGELOG.md` `0.1.0` section with full feature summary.

- **GHCR signed image**:
  - Tag `0.1.0` pushed to `ghcr.io/cms-pm/brontes-probe-mcp`.
  - cosign signature present on the `0.1.0` digest.
  - Multi-arch manifest (`linux/amd64` + `linux/arm64`).
  - `sha256:…` digest recorded in `artifacts/validation/phase-1/chunk-1.4/run_<UTC>/ghcr_digest.md`.

- **Docker MCP Catalog submission**:
  - Submit `docs/catalog/docker-mcp-catalog-manifest.yaml` per the
    rules snapshot captured in chunk 1.3.
  - Submission confirmation or PR URL recorded in evidence dir.

- **Anthropic MCP registry submission**:
  - Capture rules snapshot immediately before submission (risk R4):
    `artifacts/validation/phase-1/chunk-1.4/run_<UTC>/anthropic_mcp_registry_rules_snapshot.md`.
  - Submit entry per the rules. Submission confirmation recorded.

- **Protocol spec compatibility matrix** (spec § 5):
  - First row: `0.1.0` / container / `linux/amd64,arm64` / pinned
    pyocd version / `ghcr.io/cms-pm/brontes-probe-mcp:0.1.0@sha256:…`.

- **`PROBE_BROKER_IMAGE_DIGEST` surfacing**:
  - `session_status()` response carries correct `image_digest` and
    `image_tag` from the baked build-arg (verified in release CI).

- **Client config templates — final render**:
  - `scripts/render_client_configs.py --check` passes with the
    `0.1.0` pinned digest in the templates.

- **Evidence:** `artifacts/validation/phase-1/chunk-1.4/run_<UTC>/`

### Out of scope

- PyPI wheel publish — deferred (ratified decision; no functional
  wheel in Phase 1).
- Cockpit submodule + facade cutover — Phase 2.
- Awesome-mcp-list PRs — post-release follow-up (low-effort;
  schedule separately after Catalog approval).

## Key Design Decisions

1. **Docker MCP Catalog is primary.** If the Catalog submission is
   accepted, it is the canonical install path referenced in the
   README. If approval is delayed, the `docker run` snippet with the
   GHCR digest is the primary install path until approval lands.

2. **Anthropic registry is secondary.** Submission happens here;
   acceptance timeline is external. CHANGELOG notes both submissions.

3. **No PyPI wheel.** Ratified at 1.0. The 0.0.0 placeholder remains
   on PyPI; the functional wheel is a post-Phase-1 follow-up on
   external demand signal.

4. **Release governance.** This chunk is a release governance trigger
   per `PHASE_1_TODO.md`. Gate: signed GHCR image reachable at the
   pinned digest before the version-bump commit lands on `main`.

## Acceptance Criteria

| ID | Criterion |
|---|---|
| `SCN-1.4-VERSION` | `python -c "import brontes_probe_mcp; print(brontes_probe_mcp.__version__)"` → `0.1.0`. |
| `SCN-1.4-GHCR` | `docker pull ghcr.io/cms-pm/brontes-probe-mcp:0.1.0` succeeds. |
| `SCN-1.4-DIGEST` | `ghcr_digest.md` in evidence records `sha256:…` and it matches `docker inspect` output. |
| `SCN-1.4-COSIGN` | `cosign verify … ghcr.io/cms-pm/brontes-probe-mcp:0.1.0` exits 0. |
| `SCN-1.4-CATALOG-SUBMITTED` | Evidence records Catalog submission URL or confirmation. |
| `SCN-1.4-REGISTRY-SUBMITTED` | Evidence records Anthropic registry submission URL or confirmation. |
| `SCN-1.4-RULES-SNAPSHOT` | Evidence dir contains `anthropic_mcp_registry_rules_snapshot.md`. |
| `SCN-1.4-CHANGELOG` | `CHANGELOG.md` has `## [0.1.0]` section listing all major additions. |
| `SCN-1.4-COMPAT-MATRIX` | Protocol spec § 5 compat matrix has at least one `0.1.0` row. |
| `SCN-1.4-RENDER-CHECK` | `python scripts/render_client_configs.py --check` exits 0 with `0.1.0` digest templates. |

## Risks Activated

- **R3 (Docker MCP Catalog criteria opaque)** — submission risk.
  Mitigated by rules snapshot from chunk 1.3. If submission is
  rejected, record the rejection reason in evidence and adapt the
  manifest.
- **R4 (Anthropic MCP registry rules change)** — mitigated by
  capturing the snapshot immediately before submission in this chunk.

## File Map

New:
- `artifacts/validation/phase-1/chunk-1.4/run_<UTC>/chunk_1_4_record.md`
- `artifacts/validation/phase-1/chunk-1.4/run_<UTC>/ghcr_digest.md`
- `artifacts/validation/phase-1/chunk-1.4/run_<UTC>/anthropic_mcp_registry_rules_snapshot.md`
- `artifacts/validation/phase-1/chunk-1.4/run_<UTC>/catalog_submission.md`
- `artifacts/validation/phase-1/chunk-1.4/run_<UTC>/registry_submission.md`

Modified:
- `pyproject.toml` — version `0.1.0`
- `src/brontes_probe_mcp/__init__.py` — `__version__ = "0.1.0"`
- `CHANGELOG.md` — `[0.1.0]` section complete
- `docs/api/mcp/probe-broker-protocol.md` — compat matrix first row
- `docs/clients/*.json.j2` — digest pinned to `0.1.0` SHA256

## Rollback

Version bump can be reverted with `git revert`. The GHCR image cannot
be un-pushed (tag can be deleted; digest remains). Submission to
external registries cannot be rolled back; document as "experimental
pre-release" if needed. Rekor transparency log entries are permanent.

## Open Questions

*(Anthropic registry rules snapshot — captured immediately at chunk
open, before drafting the submission.)*
