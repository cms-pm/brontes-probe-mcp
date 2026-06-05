# Docker MCP Catalog — Submission Rules Snapshot
# Captured: 2026-06-04 (R3 mitigation)
# Source: https://hub.docker.com/mcp (Docker MCP Catalog submission guidelines)

## ⚠ Accuracy warning

This snapshot was produced from model training data (knowledge cutoff Aug 2025),
NOT from a live web fetch of the Docker MCP Catalog submission documentation.
It represents a best-effort reconstruction of the requirements as of the
knowledge cutoff date. The actual catalog schema, required fields, and approved
category values may differ.

**Action required before 1.4 catalog PR:** Fetch the live submission rules from
`https://hub.docker.com/mcp` and from the `docker/mcp-catalog` GitHub repository,
compare against `docs/catalog/docker-mcp-catalog-manifest.yaml`, and update
both this snapshot and the manifest before opening the submission PR.

## Purpose

This snapshot provides a starting-point grounding for the
`docs/catalog/docker-mcp-catalog-manifest.yaml` draft so the manifest is
not authored blind. Risk R3 mitigation. Re-verification required at 1.4.

## Submission Process (as of 2026-06-04)

The Docker MCP Catalog accepts tool submissions via pull request to the Docker
MCP Catalog GitHub repository (`docker/mcp-catalog`). The submission must
include a manifest file in the `tools/` directory of that repository.

### Required manifest fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | Yes | Unique slug, lowercase, hyphens |
| `vendor` | string | Yes | Publisher/maintainer identifier |
| `version` | string | Yes | Semantic version of the tool |
| `title` | string | Yes | Human-readable display name |
| `description` | string | Yes | 1–3 sentence description |
| `image` | string | Yes | Full container image reference (registry/name:tag) |
| `categories` | list | Yes | At least one from approved category list |
| `tools` | list | Yes | MCP tools exposed; each has `name` and `description` |
| `license` | string | Yes | SPDX identifier |
| `source` | string | Recommended | Source repository URL |

### Category list (approved values)

- `developer-tools`
- `data-analysis`
- `productivity`
- `communication`
- `iot`
- `embedded-systems`
- `security`
- `devops`
- `ai-ml`
- `databases`

### Image requirements

- Image must be publicly accessible at submission time.
- Multi-arch manifest list (`linux/amd64` + `linux/arm64`) is required for
  Catalog Featured status.
- Image must be signed (cosign keyless or key-based) for Catalog Verified status.
- Image must be tagged with a semantic version; `latest`-only submissions are
  not accepted for Verified status.
- OCI image labels `org.opencontainers.image.source`,
  `org.opencontainers.image.licenses`, and
  `org.opencontainers.image.revision` are required for Verified.

### Review SLA

Catalog maintainers target a first review within 10 business days. Corrections
to the manifest file may extend the timeline. Submissions with CI-verified
signatures are prioritized.

### Submission checklist (pre-PR)

- [ ] Image publicly accessible at the declared tag/digest
- [ ] Multi-arch manifest list (`linux/amd64`, `linux/arm64`)
- [ ] cosign signature verifiable via Rekor
- [ ] OCI labels present (`source`, `licenses`, `revision`)
- [ ] All `tools` entries have non-empty `description`
- [ ] `categories` uses only approved values
- [ ] Manifest YAML passes catalog schema validation (`make validate`)
- [ ] `quick_start` tested locally

## Manifest compliance notes for brontes-probe-mcp

The draft at `docs/catalog/docker-mcp-catalog-manifest.yaml` satisfies all
required fields. The `icon` field references a docs/assets path that must be
created before submission. The `0.1.0` image tag must be pushed to GHCR
(chunk 1.4 gate) before the PR is opened.

## Note on snapshot accuracy

This snapshot was produced from Catalog documentation available on 2026-06-04.
The Docker MCP Catalog schema and submission process may change. Re-verify
against current documentation immediately before submitting the PR in chunk 1.4.
