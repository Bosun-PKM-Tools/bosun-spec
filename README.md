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
| [`v1/trice/task.schema.json`](schemas/v1/trice/task.schema.json) | Trice (Realm 2) standalone task frontmatter: five-state lifecycle (`pending`/`active`/`done`/`dropped`/`blocked`) matching bracket markers ` `, `/`, `x`, `-`, `!`. |
| [`v1/trice/project.schema.json`](schemas/v1/trice/project.schema.json) | Trice project container grouping `$trice:task/v1` entries toward an outcome. |
| [`v1/logbook/journal.schema.json`](schemas/v1/logbook/journal.schema.json) | Logbook (Realm 3) daily scratchpad at `locker_logbook/journals/YYYY-MM-DD.md`. |
| [`v1/logbook/event.schema.json`](schemas/v1/logbook/event.schema.json) | Logbook synced calendar event record (cache/SQLite projection; optional locker note). |
| [`v1/yeoman/contact.schema.json`](schemas/v1/yeoman/contact.schema.json) | Yeoman (Realm 4) contact dossier at `locker_yeoman/contacts/<uuid>.md`. |
| [`v1/yeoman/interaction.schema.json`](schemas/v1/yeoman/interaction.schema.json) | Yeoman interaction note; `$pkm.relations` must include at least one `type: contact` UUID. |
| [`v1/commonplace/work.schema.json`](schemas/v1/commonplace/work.schema.json) | Commonplace (Realm 18) media work at `locker_commonplace/works/<slug>.md` with multi-service `external_ids`. |
| [`v1/relations/relations.schema.json`](schemas/v1/relations/relations.schema.json) | Typed `$pkm.relations` object: canonical predicate verbs with `urn:<realm>:<entity_type>:<uuid>` targets. |
| [`v1/rpc/fleet-matrix.json`](schemas/v1/rpc/fleet-matrix.json) | JSON-RPC 2.0 fleet method matrix (16 Yeoman/Trice/Logbook/Commonplace methods) plus Draft 2020-12 envelope/`$defs` schemas. |

Canonical `$id` URIs are `https://bosunpkm.com/schemas/<path-from-schemas/>`.

### Fixtures (`fixtures/`)

Golden CommonMark examples with YAML frontmatter that satisfies the corresponding v1 schemas:

| File | Description |
|---|---|
| [`trice/sample-task.md`](fixtures/trice/sample-task.md) | `$trice:task/v1` note demonstrating all five task-line bracket markers. |
| [`logbook/2026-09-16.md`](fixtures/logbook/2026-09-16.md) | Daily journal with agenda transclusion blocks and time-blocked tasks. |
| [`yeoman/jane-doe.md`](fixtures/yeoman/jane-doe.md) | Contact dossier with structured channels. |
| [`commonplace/dune.md`](fixtures/commonplace/dune.md) | Media record with multi-service external IDs. |
| [`relations/task-delegated.md`](fixtures/relations/task-delegated.md) | Trice task whose `$pkm.relations.assignedToContact` targets a Yeoman contact URN. |
| [`relations/event-attended.md`](fixtures/relations/event-attended.md) | Meeting note whose `$pkm.relations.attendedEvent` targets a Logbook event URN. |

Canonical ingestion codec samples (upstream export bytes, not locker notes). RFC documents use CRLF and 75-octet folding; Kindle clippings keep a UTF-8 BOM. Integrity checks live in [`tests/test_codec_fixtures.py`](tests/test_codec_fixtures.py).

| File | Description |
|---|---|
| [`codecs/vcard/contacts-v3.vcf`](fixtures/codecs/vcard/contacts-v3.vcf) | Multi-card vCard 3.0 Apple export with `item1.X-ABLabel:CustomPhone` and base64 `PHOTO;ENCODING=b;TYPE=JPEG`. |
| [`codecs/vcard/contacts-v4.vcf`](fixtures/codecs/vcard/contacts-v4.vcf) | Multi-card vCard 4.0 export with URI-referenced avatars. |
| [`codecs/ical/agenda-complex.ics`](fixtures/codecs/ical/agenda-complex.ics) | RFC 5545 calendar: daily/weekly `RRULE` + `EXDATE`, multi-day spans, RSVP attendees, local `VJOURNAL`. |
| [`codecs/tasks/todoist-export.json`](fixtures/codecs/tasks/todoist-export.json) | Todoist backup: nested `parent_id`, priorities 1–4 (p4–p1), recurring dues, project assignment. |
| [`codecs/tasks/things-export.json`](fixtures/codecs/tasks/things-export.json) | Things 3 dump: areas/projects/headings, deadlines, and checklist items. |
| [`codecs/media/goodreads-sample.csv`](fixtures/codecs/media/goodreads-sample.csv) | Goodreads export CSV with mixed ISBN-10/13, read dates, star ratings, and custom shelves. |
| [`codecs/media/kindle-clippings.txt`](fixtures/codecs/media/kindle-clippings.txt) | Kindle `My Clippings.txt` with UTF-8 BOM, page/location offsets, and multi-session highlights. |

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
python tests/test_codec_fixtures.py
python tests/test_relations_spec.py
```

---

## Schema Validation

The [`tests/test_schemas.py`](tests/test_schemas.py) script verifies that all JSON schemas in `schemas/` (including nested `v1/<realm>/*.schema.json` files) are:

1. Valid JSON (no syntax errors).
2. Recognised JSON Schema drafts (`$schema` field present).
3. Well-formed under `jsonschema.check_schema()` (Draft 2020-12 meta-schema validation).

Run it with:

```bash
python tests/test_schemas.py
# or
python -m pytest tests/ -v
```

[`tests/test_codec_fixtures.py`](tests/test_codec_fixtures.py) checks that every file under `fixtures/codecs/` is valid UTF-8, that vCard/iCalendar documents use CRLF with 75-octet folding, and that Kindle clippings start at the UTF-8 BOM byte boundary.

```bash
python tests/test_codec_fixtures.py
```

[`tests/test_relations_spec.py`](tests/test_relations_spec.py) extracts `$pkm.relations` from the relations fixtures, validates them against `relations.schema.json`, and checks that `fleet-matrix.json` catalogs all sixteen JSON-RPC methods.

```bash
python tests/test_relations_spec.py
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
