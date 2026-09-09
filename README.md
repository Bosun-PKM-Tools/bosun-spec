# Bosun PKM — Open Specification

**Repository**: `Bosun-PKM-Tools/bosun-spec`  
**Status**: Active Draft  
**License**: MIT

---

## What This Is

`bosun-spec` is the **public open specification** for the Bosun PKM knowledge portability standard. It defines the machine-readable contracts, event vocabulary, and protocol RFCs that allow independently developed tools — importers, exporters, browser extensions, desktop clients, and CLI utilities — to interoperate cleanly with the Bosun PKM ecosystem.

This repository contains **only schemas, RFCs, and documentation**. No storage implementations, engine adapters, or proprietary code are included.

---

## Specification Documents

### Schemas (`schemas/`)

| File | Description |
|---|---|
| [`canonical-note-contract-v0.1.json`](schemas/canonical-note-contract-v0.1.json) | JSON Schema (Draft 2020-12) defining the canonical note frontmatter contract: required fields, timestamp format, tag structure, provenance, lineage, and relationship graph. |
| [`event-vocab-v0.1.json`](schemas/event-vocab-v0.1.json) | JSON Schema defining the machine-readable event vocabulary: error codes, warning codes, severity levels, and structured payload schemas for all pipeline lifecycle events. |

### Reference Documentation (`docs/`)

| File | Description |
|---|---|
| [`event-vocab-v0.md`](docs/event-vocab-v0.md) | Human-readable narrative companion to `event-vocab-v0.1.json`. Covers the full event catalog by severity, the standard event envelope format, and the runtime event mapping table. |
| [`harbormaster-protocol-v1-rfc.md`](docs/harbormaster-protocol-v1-rfc.md) | RFC draft for the Harbormaster Protocol v1: the strictly read-only loopback HTTP API for local module integration. Covers threat model, capability grants, handshake lifecycle, endpoint catalog, security invariants, and rate-limiting. |

---

## Core Concepts

### Local-First Note Portability

Bosun PKM is a local-first knowledge operating system. Notes never leave the user's machine unless the user explicitly chooses to export them. The canonical note contract defines a stable, portable intermediate representation that any importer, exporter, or adapter can target without coupling to a specific storage backend or app format.

### Canonical Note Contract

Every note processed through the Bosun pipeline is normalized into a `CanonicalNote` — a structured object with YAML frontmatter conforming to [`canonical-note-contract-v0.1.json`](schemas/canonical-note-contract-v0.1.json).

Key fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | integer (`1`) | ✅ | Contract major version. |
| `type` | string (`"note"`) | ✅ | Entity classification. |
| `title` | string | ✅ | Human-readable note title. |
| `status` | string (`"active"`) | ✅ | Operational lifecycle status. |
| `source` | string | ✅ | Originating tool or importer (e.g. `"evernote"`, `"obsidian"`, `"web-clip"`). |
| `source_id` | string | ✅ | Stable upstream GUID or identifier. |
| `created_at` | string | ✅ | UTC timestamp (`YYYYMMDDHHMMSS`) or raw wire value if unparseable. |
| `updated_at` | string | ✅ | UTC timestamp (`YYYYMMDDHHMMSS`) or raw wire value if unparseable. |
| `tags` | string[] | ✅ | User-defined tags. |
| `canonical_format` | string (`"markdown-yaml"`) | ✅ | Output file format standard. |
| `content_format` | `"html"` \| `"markdown"` | ✅ | Highest-fidelity body representation. |
| `target_app` | `"any"` \| `"obsidian"` \| `"logseq"` | ✅ | Downstream target application. |
| `relations` | object[] | — | Typed directed graph edges to other notes. |
| `provenance` | object | — | Origin and lineage metadata for auditability. |
| `lineage` | object[] | — | Ordered transformation history across tools. |

### Event Vocabulary

All pipeline tools emit structured events conforming to [`event-vocab-v0.1.json`](schemas/event-vocab-v0.1.json). Events follow a four-level severity hierarchy:

| Severity | Identifier | Semantics |
|---|---|---|
| Fatal | `fatal` | Unrecoverable failure. Halts the batch. |
| Error | `error` | Entity-level failure. Batch continues. |
| Warning | `warn` | Partial degradation. Entity is preserved. |
| Info | `info` | Normal lifecycle milestone. |

Each event is emitted as a standard envelope:

```json
{
  "event": "warn.timestamp.unparseable",
  "severity": "warn",
  "timestamp": "2026-09-03T18:00:00Z",
  "payload": {
    "title": "Meeting Notes",
    "field": "created",
    "raw_value": "yesterday-ish"
  }
}
```

### Harbormaster Protocol v1 (RFC Draft)

The [Harbormaster Protocol v1 RFC](docs/harbormaster-protocol-v1-rfc.md) specifies a strictly **read-only** loopback HTTP API for connecting independently running native modules (desktop clients, CLI utilities, status bar extensions) to a local Harbor engine instance.

Key invariants:
- **Loopback-only**: Binds exclusively to literal IPv4 `127.0.0.1`. Never exposes a public interface.
- **Read-only in v1**: No endpoint may create, modify, or delete notes, files, or engine state.
- **Capability-gated**: All access requires a capability-scoped bearer token approved by the local operator. Capabilities are deny-by-default.
- **Cryptographic identity**: Module identity is established via Ed25519 public key, not display strings.

---

## Implementing Against This Standard

### For Importers and Exporters

1. Validate your output frontmatter against [`schemas/canonical-note-contract-v0.1.json`](schemas/canonical-note-contract-v0.1.json) using any JSON Schema Draft 2020-12-compatible validator.
2. Emit structured events conforming to [`schemas/event-vocab-v0.1.json`](schemas/event-vocab-v0.1.json) for observability and interoperability.
3. Reference [`docs/event-vocab-v0.md`](docs/event-vocab-v0.md) for the human-readable event catalog.

### For Protocol Integrators

1. Read the [Harbormaster Protocol v1 RFC](docs/harbormaster-protocol-v1-rfc.md) in full before beginning implementation.
2. Note the **Implementation Gate** (§1.3): implementation cannot begin until explicit owner approval of the draft, merged schema PR, and resolved benchmark decisions.

### Schema Validation (Quick Start)

```bash
pip install jsonschema
python tests/test_schemas.py
```

---

## Schema Validation

The [`tests/test_schemas.py`](tests/test_schemas.py) script verifies that all JSON schemas in `schemas/` are:

1. Valid JSON (no syntax errors).
2. Recognised JSON Schema drafts (`$schema` field present).
3. Well-formed under `jsonschema.check_schema()` (Draft 2020-12 meta-schema validation).

Run it with:

```bash
python tests/test_schemas.py
# or
python -m pytest tests/ -v
```

---

## Versioning & Compatibility

Schemas follow semantic versioning (`v0.1`, `v0.2`, ..., `v1.0`). Breaking changes to required fields increment the major version. Additive optional fields are backward-compatible.

See [Compatibility Policy](https://github.com/Bosun-PKM-Tools/bosun-pkm/blob/main/docs/schema/compatibility-policy.md) (in the main monorepo) for the full evolution discipline.

---

## Contributing

This repository accepts:
- Issue reports for schema ambiguities or RFC gaps.
- Pull requests adding new optional fields, event codes, or clarifying documentation.
- Proposed extensions following the versioning policy above.

Please open an issue before submitting a PR for any breaking or structural change.

---

## License

MIT — see [LICENSE](LICENSE).
