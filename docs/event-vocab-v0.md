# Bosun PKM — Event Vocabulary Contract (v0)

Status: Active draft  
Version: 0.1.0  
Scope: Machine-readable event taxonomy, error/warning codes, severity levels, and structured payload schemas for Bosun PKM importers, converters, and exporters.

---

## 1. Severity Levels

Every emitted event conforms to one of four hierarchical severity levels:

| Level | Identifier | Semantics | Flow Control |
|---|---|---|---|
| **Fatal** | `fatal` | Unrecoverable container or environment failure. | Halts batch operation immediately. |
| **Error** | `error` | Failure confined to an individual entity (e.g. note). | Fails current entity; batch continues. |
| **Warning** | `warn` | Parse ambiguity, partial degradation, or unmapped tag. | Entity is preserved and written; warning logged. |
| **Info** | `info` | Normal lifecycle milestone or idempotent skip. | Informational only. |

---

## 2. Event Catalog

### 2.1 Fatal Container & System Events (`fatal`)

#### `err.file.not_found`
- **Legacy Code**: `ERR_INVALID_FILE`
- **Severity**: `fatal`
- **Description**: The specified input archive or file path does not exist on disk.
- **Payload Schema**:
  ```json
  {
    "path": "string (filepath that failed resolution)",
    "message": "string (human-readable explanation)"
  }
  ```

#### `err.parse.failed`
- **Legacy Code**: `ERR_PARSING_FAILED`
- **Severity**: `fatal`
- **Description**: Container document (e.g. ENEX XML) is corrupt, truncated, or unparseable.
- **Payload Schema**:
  ```json
  {
    "path": "string (filepath that failed parsing)",
    "message": "string (human-readable explanation)"
  }
  ```

#### `err.vault.invalid`
- **Legacy Code**: `ERR_INVALID_VAULT`
- **Severity**: `fatal`
- **Description**: Target vault path cannot be initialized, written to, or verified.
- **Payload Schema**:
  ```json
  {
    "vault_path": "string (vault directory path)",
    "message": "string (human-readable explanation)"
  }
  ```

---

### 2.2 Note-Level Error Events (`error`)

#### `err.db.operation`
- **Legacy Code**: `ERR_DB_OPERATION`
- **Severity**: `error`
- **Description**: Database query, constraint check, or upsert failed for a specific note.
- **Payload Schema**:
  ```json
  {
    "id": "string (upstream note ID / GUID)",
    "title": "string (note title)",
    "message": "string (database error details)"
  }
  ```

#### `err.write.failed`
- **Legacy Code**: `ERR_WRITE_FAILED`
- **Severity**: `error`
- **Description**: File system write operation for note Markdown or assets failed after retries were exhausted.
- **Payload Schema**:
  ```json
  {
    "id": "string (upstream note ID / GUID)",
    "title": "string (note title)",
    "message": "string (write failure reason)"
  }
  ```

#### `err.engine.run_failed`
- **Legacy Code**: `ERR_ENGINE_RUN_FAILED`
- **Severity**: `error`
- **Description**: Engine execution pipeline failed fatally during an active run.
- **Payload Schema**:
  ```json
  {
    "run_id": "string (unique pipeline run identifier)",
    "stage": "string (ingest | canonicalize | validate | export)",
    "code": "string (standard error code triggering failure)",
    "message": "string (failure description)"
  }
  ```

#### `err.stage.failed`
- **Legacy Code**: `ERR_STAGE_FAILED`
- **Severity**: `error`
- **Description**: Pipeline stage processing encountered an unrecoverable failure.
- **Payload Schema**:
  ```json
  {
    "run_id": "string (unique pipeline run identifier)",
    "stage": "string (stage identifier)",
    "code": "string (failure code)",
    "message": "string (failure explanation)"
  }
  ```

#### `err.validation.failed`
- **Legacy Code**: `ERR_VALIDATION_FAILED`
- **Severity**: `error`
- **Description**: Note canonical frontmatter validation failed against schema invariants.
- **Payload Schema**:
  ```json
  {
    "path": "string (relative path of invalid note file)",
    "message": "string (validation failure message)"
  }
  ```

---

### 2.3 Warning Events (`warn`)

#### `warn.timestamp.unparseable`
- **Legacy Code**: `WARN_UNPARSEABLE_TIMESTAMP`
- **Severity**: `warn`
- **Description**: A timestamp string does not conform to ENEX (`YYYYMMDDTHHMMSSZ`), canonical (`YYYYMMDDHHMMSS`), or ISO-8601 formats. The raw wire value is preserved in frontmatter.
- **Payload Schema**:
  ```json
  {
    "title": "string (note title)",
    "field": "string ('created' | 'updated')",
    "raw_value": "string (the unparseable string encountered)"
  }
  ```

#### `warn.media.incomplete`
- **Legacy Code**: `WARN_INCOMPLETE_MEDIA`
- **Severity**: `warn`
- **Description**: An `<en-media>` tag in the note content lacks either a `hash` or `type` attribute. A placeholder is generated with `warning="missing-attrs"`.
- **Payload Schema**:
  ```json
  {
    "title": "string (note title)",
    "index": "integer (0-based order index in document)",
    "warning": "string ('missing-attrs')"
  }
  ```

#### `warn.media.unresolved`
- **Legacy Code**: `WARN_UNRESOLVED_MEDIA`
- **Severity**: `warn`
- **Description**: *(Provisional)* An inline `<en-media>` placeholder's hash does not match any `<resource>` attachment in the archive.
- **Payload Schema**:
  ```json
  {
    "id": "string (upstream note ID / GUID)",
    "hash": "string (unmatched hash)",
    "mime": "string (MIME type)"
  }
  ```

#### `warn.media.unresolved_hash`
- **Legacy Code**: `WARN_UNRESOLVED_MEDIA_HASH`
- **Severity**: `warn`
- **Description**: An `[EN_MEDIA]` hash did not join to known resource/attachment metadata.
- **Payload Schema**:
  ```json
  {
    "note": "string (note title)",
    "hash": "string (unmatched hash)",
    "index": "integer (0-based order index in document)"
  }
  ```

#### `warn.markdown.nondeterministic`
- **Legacy Code**: `WARN_NONDETERMINISTIC_MARKDOWN`
- **Severity**: `warn`
- **Description**: Markdown emphasis could not be reconstructed deterministically (such as `***` nested spans) and was left as text.
- **Payload Schema**:
  ```json
  {
    "note": "string (note title)"
  }
  ```

---

### 2.4 Informational Events (`info`)

#### `info.note.skipped`
- **Legacy Code**: `INFO_NOTE_SKIPPED`
- **Severity**: `info`
- **Description**: Note import skipped because its content SHA256 matches an existing imported note record.
- **Payload Schema**:
  ```json
  {
    "id": "string (upstream note ID / GUID)",
    "title": "string (note title)",
    "reason": "string ('already_imported')"
  }
  ```

#### `info.engine.run_started`
- **Legacy Code**: `INFO_ENGINE_RUN_STARTED`
- **Severity**: `info`
- **Description**: Engine execution pipeline started a new transformation run.
- **Payload Schema**:
  ```json
  {
    "run_id": "string (unique pipeline run identifier)",
    "source": "string (source archive or path)",
    "vault": "string (destination vault path)",
    "target": "string (target application, e.g. obsidian)"
  }
  ```

#### `info.engine.run_completed`
- **Legacy Code**: `INFO_ENGINE_RUN_COMPLETED`
- **Severity**: `info`
- **Description**: Engine execution pipeline finished successfully.
- **Payload Schema**:
  ```json
  {
    "run_id": "string (unique pipeline run identifier)",
    "imported_count": "integer (count of imported notes)",
    "skipped_count": "integer (count of skipped notes)",
    "failed_count": "integer (count of failed notes)"
  }
  ```

#### `info.stage.started`
- **Legacy Code**: `INFO_STAGE_STARTED`
- **Severity**: `info`
- **Description**: Pipeline stage processing started.
- **Payload Schema**:
  ```json
  {
    "run_id": "string (unique pipeline run identifier)",
    "stage": "string (ingest | canonicalize | validate | export)"
  }
  ```

#### `info.stage.completed`
- **Legacy Code**: `INFO_STAGE_COMPLETED`
- **Severity**: `info`
- **Description**: Processing for a specific pipeline stage finished successfully.
- **Payload Schema**:
  ```json
  {
    "run_id": "string (unique pipeline run identifier)",
    "stage": "string (stage identifier)"
  }
  ```

#### `info.note.imported`
- **Legacy Code**: `INFO_NOTE_IMPORTED`
- **Severity**: `info`
- **Description**: Note successfully converted and written into canonical vault representation.
- **Payload Schema**:
  ```json
  {
    "id": "string (upstream note ID / GUID)",
    "title": "string (note title)",
    "vault_path": "string (relative file path in vault)"
  }
  ```

---

### 2.5 Protocol v1 Audit Events (Reserved Vocabulary)

The following events are registered as reserved audit vocabulary for the future approved Harbormaster Protocol v1 implementation. They are not currently emitted by the production engine.

#### `info.protocol.handshake`
- **Legacy Code**: `INFO_PROTOCOL_HANDSHAKE`
- **Severity**: `info`
- **Description**: Protocol handshake approved and session token issued. Reserved for future approved Protocol v1 implementation.
- **Payload Schema**:
  ```json
  {
    "client_id": "string (authenticated client identifier)",
    "module_public_key": "string (client module public key)",
    "capabilities_granted": "array of strings (approved capability strings)",
    "locker_id": "string (target locker identifier)"
  }
  ```

#### `warn.protocol.unauthorized`
- **Legacy Code**: `WARN_UNAUTHORIZED_ACCESS`
- **Severity**: `warn`
- **Description**: Request rejected due to invalid, missing, or expired token. Reserved for future approved Protocol v1 implementation.
- **Payload Schema**:
  ```json
  {
    "path": "string (request path that failed authorization)",
    "reason": "string (rejection reason description)"
  }
  ```

#### `warn.protocol.forbidden_host`
- **Legacy Code**: `WARN_FORBIDDEN_HOST`
- **Severity**: `warn`
- **Description**: Request rejected due to non-loopback or non-literal Host header. Reserved for future approved Protocol v1 implementation.
- **Payload Schema**:
  ```json
  {
    "host_header": "string (rejected Host header value)"
  }
  ```

#### `warn.protocol.capability_denied`
- **Legacy Code**: `WARN_CAPABILITY_DENIED`
- **Severity**: `warn`
- **Description**: Request rejected due to missing capability grant. Reserved for future approved Protocol v1 implementation.
- **Payload Schema**:
  ```json
  {
    "client_id": "string (client identifier)",
    "required_capability": "string (capability required by the operation)",
    "granted_capabilities": "array of strings (capabilities currently held by client)"
  }
  ```

#### `warn.protocol.stream_lag`
- **Legacy Code**: `WARN_STREAM_CLIENT_LAG`
- **Severity**: `warn`
- **Description**: SSE client dropped due to ring buffer overflow. Reserved for future approved Protocol v1 implementation.
- **Payload Schema**:
  ```json
  {
    "client_id": "string (slow subscriber identifier)",
    "dropped_count": "integer (number of messages dropped before disconnect)"
  }
  ```

---

## 3. Emitted Event Envelope

When structured JSON telemetry or audit streams are enabled, events are wrapped in the standard envelope:

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

---

## 4. Runtime Event Mapping Table (Ingest, Status, Health, Adapter Operations)

The following matrix maps runtime lifecycle actions across Harbormaster, adapters, and the HTTP daemon to canonical schema event vocabulary:

| Operational Category | Operation / Trigger | Legacy Code | Canonical Event Name | Severity | Flow Control | Primary Payload Fields |
|---|---|---|---|---|---|---|
| **Ingest (Run)** | Pipeline job begins | `INFO_ENGINE_RUN_STARTED` | `info.engine.run_started` | `info` | Normal flow | `run_id`, `source`, `vault`, `target` |
| **Ingest (Run)** | Pipeline job finishes | `INFO_ENGINE_RUN_COMPLETED` | `info.engine.run_completed` | `info` | Normal flow | `run_id`, `imported_count`, `skipped_count`, `failed_count` |
| **Ingest (Run)** | Pipeline fails fatally | `ERR_ENGINE_RUN_FAILED` | `err.engine.run_failed` | `error` | Run aborts | `run_id`, `stage`, `code`, `message` |
| **Ingest (Stage)** | Stage begins (`ingest`, `canonicalize`, etc.) | `INFO_STAGE_STARTED` | `info.stage.started` | `info` | Normal flow | `run_id`, `stage` |
| **Ingest (Stage)** | Stage finishes cleanly | `INFO_STAGE_COMPLETED` | `info.stage.completed` | `info` | Normal flow | `run_id`, `stage` |
| **Ingest (Stage)** | Stage fails | `ERR_STAGE_FAILED` | `err.stage.failed` | `error` | Stage halts | `run_id`, `stage`, `code`, `message` |
| **Adapter Ops** | Note parsed & written to vault | `INFO_NOTE_IMPORTED` | `info.note.imported` | `info` | Continue batch | `id`, `title`, `vault_path` |
| **Adapter Ops** | Idempotent note skip (hash match) | `INFO_NOTE_SKIPPED` | `info.note.skipped` | `info` | Continue batch | `id`, `title`, `reason` |
| **Adapter Ops** | Unresolved source archive | `ERR_INVALID_FILE` | `err.file.not_found` | `fatal` | Immediate abort | `path`, `message` |
| **Adapter Ops** | Corrupted container data | `ERR_PARSING_FAILED` | `err.parse.failed` | `fatal` | Immediate abort | `path`, `message` |
| **Adapter Ops** | Note write failure on disk | `ERR_WRITE_FAILED` | `err.write.failed` | `error` | Note fails | `id`, `title`, `message` |
| **Adapter Ops** | Ambiguous timestamp format | `WARN_UNPARSEABLE_TIMESTAMP` | `warn.timestamp.unparseable` | `warn` | Preserved as-is | `title`, `field`, `raw_value` |
| **Validation** | Canonical note fails schema invariants | `ERR_VALIDATION_FAILED` | `err.validation.failed` | `error` | Note flagged | `path`, `message` |
| **Protocol v1 (Audit)** | Handshake approved & token issued | `INFO_PROTOCOL_HANDSHAKE` | `info.protocol.handshake` | `info` | Normal flow | `client_id`, `module_public_key`, `capabilities_granted`, `locker_id` |
| **Protocol v1 (Audit)** | Token missing, invalid, or expired | `WARN_UNAUTHORIZED_ACCESS` | `warn.protocol.unauthorized` | `warn` | HTTP 401 | `path`, `reason` |
| **Protocol v1 (Audit)** | Host header not literal loopback | `WARN_FORBIDDEN_HOST` | `warn.protocol.forbidden_host` | `warn` | HTTP 403 | `host_header` |
| **Protocol v1 (Audit)** | Endpoint requires ungranted cap | `WARN_CAPABILITY_DENIED` | `warn.protocol.capability_denied` | `warn` | HTTP 403 | `client_id`, `required_capability`, `granted_capabilities` |
| **Protocol v1 (Audit)** | SSE subscriber lagged buffer | `WARN_STREAM_CLIENT_LAG` | `warn.protocol.stream_lag` | `warn` | Drop client | `client_id`, `dropped_count` |
| **Health** | `/health` endpoint probe | *(internal)* | `info.health.checked` | `info` | HTTP 200/503 | `status`, `uptime_seconds`, `adapters` |
| **Status** | `/api/status` daemon query | *(internal)* | `info.status.queried` | `info` | HTTP 200 | `service`, `pid`, `uptime_seconds`, `recent_events` |
| **Dispatch Bus** | Event daemon starts | *(in-process)* | `dispatch.started` | `info` | Normal flow | `message`, `host`, `port` |
| **Dispatch Bus** | Event daemon stops | *(in-process)* | `dispatch.completed` | `info` | Normal flow | `message` |

---

## 5. Related Documentation & Schema Contracts

- **Canonical Note Contract**: [canonical-note-contract-v0.md](file:///c:/dev/repos/bosun-pkm/docs/schema/canonical-note-contract-v0.md) — Specification for intermediate note representation, required/optional frontmatter fields, and schema invariants.
- **Harbormaster Runtime & Operator Guide**: [operator-runtime-guide.md](file:///c:/dev/repos/bosun-pkm/apps/harbormaster/docs/operator-runtime-guide.md) — Service daemon lifecycle, health monitoring, and adapter execution.
- **Engine Pipeline & CLI Specification**: [bosun-engine.md](file:///c:/dev/repos/bosun-pkm/apps/harbormaster/docs/bosun-engine.md) — Pipeline architecture, stages, and CLI invocation.
- **Compatibility Policy**: [compatibility-policy.md](file:///c:/dev/repos/bosun-pkm/docs/schema/compatibility-policy.md) — Evolution discipline, drift prevention rules, and backward compatibility invariants.

---

## 6. Integration Status

| Event Subsystem | Status | Production Guarantees & Scope |
| :--- | :--- | :--- |
| **Core Error & Warning Catalog** | `Production-Ready` | Fully defined taxonomy covering fatal container errors, entity-level write/parse errors, and non-fatal warnings with structured machine-readable fields. |
| **Engine & Stage Lifecycle Events** | `Production-Ready` | 8 operational events (`info.engine.run_started`, `info.engine.run_completed`, `err.engine.run_failed`, `info.stage.started`, `info.stage.completed`, `err.stage.failed`, `info.note.imported`, `err.validation.failed`) added and mapped. |
| **Protocol v1 Audit Events** | `Reserved` | 5 audit event codes defined in schema contract v0.1 as reserved vocabulary for future Protocol v1 implementation. |
| **Bidirectional Harbormaster Mapping** | `Production-Ready` | Bidirectional conversion utilities in `apps/harbormaster/harbormaster/src/bosun_engine/reporters/events.py` translate internal events to schema events cleanly. |
| **Drift Prevention Enforcement** | `Production-Ready` | CI drift tests verify JSON Schema, Python catalogs, and snapshot fixtures remain 100% synchronized. |
| **Distributed Multi-Tenant Event Streams** | `Pending` | Streaming cross-datacenter event replication is deferred to v1.0. |
