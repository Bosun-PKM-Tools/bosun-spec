# Fleet specification contracts

Canonical JSON Schema and JSON-RPC 2.0 contracts for Bosun PKM. Runtime engines
must conform to these documents; `bosun-spec` is the single source of truth.

Related machine-readable catalogs:

- [`schemas/v1/rpc/fleet-matrix.json`](../schemas/v1/rpc/fleet-matrix.json) — method catalog
- [`schemas/v1/rpc/error-envelope.schema.json`](../schemas/v1/rpc/error-envelope.schema.json) — error envelope
- [`schemas/v1/meta/envelope.schema.json`](../schemas/v1/meta/envelope.schema.json) — `$pkm` frontmatter
- [`schemas/v1/realms/12-galley.schema.json`](../schemas/v1/realms/12-galley.schema.json) — recipe / provenance
- [`schemas/v1/query/graph-neighborhood-query.schema.json`](../schemas/v1/query/graph-neighborhood-query.schema.json) — harbormaster graph query
- [`schemas/v1/query/federated-query-plan.runtime.schema.json`](../schemas/v1/query/federated-query-plan.runtime.schema.json) — harbormaster federated plan

The full Graph DSL (`graph-dsl.schema.json`) and federated plan
(`federated-query-plan.schema.json`) remain the richer specification surface.
Harbormaster currently implements the **runtime** neighborhood / sites-queries
projections above.

---

## 1. Transport: JSON-RPC 2.0 over stdio NDJSON (KPP)

KPP is **not** HTTP and **not** a socket protocol.

| Rule | Contract |
|------|----------|
| Framing | One JSON-RPC 2.0 object per stdin line; one response per stdout line |
| Version | `"jsonrpc": "2.0"` required |
| Params style | Named object only. Arrays are rejected (`-32602`) |
| Batches | JSON arrays are rejected (`-32600`, “batch requests are not supported”) |
| Notifications | Request with no `id` produces **no** stdout line |
| Id | Request/response methods require `id` as string or number |
| Encoding | UTF-8, newline-delimited (`\n`) |

Example request:

```json
{"jsonrpc":"2.0","id":1,"method":"marlinspike.ping","params":{}}
```

Success response:

```json
{"jsonrpc":"2.0","id":1,"result":{"pong":true,"adapter":"marlinspike-kpp","version":"0.1.0"}}
```

Error response:

```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"Method not found","data":"marlinspike.nope"}}
```

### Shared error codes

| Code | Name | When |
|------|------|------|
| `-32700` | Parse error | Line is not JSON |
| `-32600` | Invalid Request | Missing `method`, `jsonrpc` ≠ `"2.0"`, or batch array |
| `-32601` | Method not found | Unknown method name |
| `-32602` | Invalid params | Missing/typed-wrong named params |
| `-32603` | Internal error | Transport timeout / unexpected fault |
| `-32000` | Application / schema | I/O, CST surgery failure, or schema validation |
| `-32001` | Vault locked | Crypto / lock contention |
| `-32002` | Orphan URN | Relation target not in vault |
| `-32007` | Method not allowed | Harbormaster vessel allowlist rejection |

---

## 2. Marlinspike CST engine (`marlinspike-kpp`)

Source of truth: `marlinspike/crates/marlinspike-kpp/src/server.rs`, tested in
`crates/marlinspike-kpp/tests/test_kpp_dispatch.rs` and exercised by
`harbormaster` adapters.

Adapter ping identity: `adapter` = `marlinspike-kpp`, `version` = `0.1.0`.

Frontmatter patches are trivia-preserving Rowan splices. Nested objects under
`$pkm`, `$realm` / `$lore`, `$recipe`, and `$nutrition` are addressed as JSON
objects. List entries use numeric path segments (`$recipe.ingredients.0.quantity`).
The Markdown body, including trailing whitespace and CRLF, is never rewritten.

| Method | Mutates | Params | Result |
|--------|---------|--------|--------|
| `marlinspike.ping` | no | `{}` (params optional at the wire; catalog uses `{}`) | `{pong: true, adapter: "marlinspike-kpp", version: "0.1.0"}` |
| `marlinspike.parse_ast` | no | `{path: string}` | Syntax tree object plus `path`, `errors` |
| `marlinspike.parse_cst` | no | `{path: string}` | Alias of `parse_ast` |
| `marlinspike.patch_frontmatter` | yes | `{path: string, patch: object}` | `{ok: true, patched: true, path}` |
| `marlinspike.scale_recipe` | yes | `{path: string, factor: number}` | `{ok: true, scaled: true, factor, path}` |
| `marlinspike.scale_nutrition` | yes | `{path: string, factor: number}` | `{ok: true, scaled: true, factor, path}` |
| `marlinspike.convert_units` | yes | `{path: string, target_system: "metric"\|"imperial"}` | `{ok: true, converted: true, target_system, path}` |
| `marlinspike.reorder_steps` | yes | `{path: string, order: number[]}` | `{ok: true, reordered: true, order, path}` |
| `marlinspike.insert_step` | yes | `{path: string, index: integer>=0, content: string}` | `{ok: true, inserted: true, index, path}` |

`patch` example (matches the KPP dispatch test):

```json
{
  "path": "fixtures/notes/dual_scope_crlf.md",
  "patch": {
    "$pkm": {"title": "KPP Patched"},
    "$realm": {"zone": "harbor-gate"}
  }
}
```

### Harbormaster router vs engine

`harbormaster` `VESSEL_METHOD_ALLOWLISTS["marlinspike"]` is a **security subset**
of the engine:

| Method | Engine | Harbormaster allowlist |
|--------|--------|------------------------|
| `marlinspike.ping` | yes | yes |
| `marlinspike.parse_ast` | yes | yes |
| `marlinspike.parse_cst` | yes | yes |
| `marlinspike.patch_frontmatter` | yes | yes |
| `marlinspike.scale_nutrition` | yes | yes |
| `marlinspike.scale_recipe` | yes | no |
| `marlinspike.convert_units` | yes | no |
| `marlinspike.reorder_steps` | yes | no |
| `marlinspike.insert_step` | yes | no |
| `marlinspike.extract_tokens` | **no** | yes (adapter helper only; engine returns `-32601`) |

The spec catalogs the **engine** contract. Router allowlists may be narrower.

---

## 3. Other active stdio engines

These methods are implemented and tested. Realm catalog entries in
`fleet-matrix.json` (for example `galley.check_pantry`,
`charthouse.query_timeline`) remain the planned domain surface and are **not**
replaced by the engine tables below.

### Galley (`src/galley/rpc_server.py`)

| Method | Notes |
|--------|-------|
| `galley.ping` | Returns `"pong"` |
| `galley.list_methods` | Method name list |
| `galley.scale_recipe` | Also in fleet-matrix (catalog params use `recipe_id` / `target_servings`) |
| `galley.deplete_pantry` | Mutating pantry update |
| `galley.generate_manifest` | Shopping / cook manifest |
| `galley.calculate_nutritional_score` / `galley.score_recipe` | Aliases |
| `galley.scan_recipe_allergens` / `galley.scan_allergens` | Aliases |
| `galley.filter_mealplan_recipes` / `galley.filter_recipes` | Aliases |

Harbormaster galley allowlist today: `galley.ping`, `galley.get_recipe`,
`galley.search_ingredients` (the latter two are adapter helpers, not listed by
`galley.list_methods`).

### Tender (`apps/tender/src/kpp/server.py`)

`tender.clip`, `tender.inspect_archive`, `tender.queue_list`, `tender.promote`,
`tender.reject`, `tender.search`, plus adapter `tender.ping` /
`tender.ingest_clip` / `tender.extract_article`.

### Charthouse (`crates/charthouse-kpp/src/server.rs`)

`charthouse.ping`, `charthouse.check_continuity`, `charthouse.compile_binder`,
`charthouse.inspect_board`, `charthouse.render_board_svg`,
`charthouse.inspect_outline`, `charthouse.inspect_branch`,
`charthouse.render_map`, `charthouse.doctor`.

### Harbormaster graph worker

`bosun.graph_query` — neighborhood query over locker notes. Params match
`graph-neighborhood-query.schema.json`. Result: `{from, depth, nodes, edges}`.

---

## 4. `$pkm` frontmatter blocks

Canonical envelope: [`schemas/v1/meta/envelope.schema.json`](../schemas/v1/meta/envelope.schema.json).

Required on the spec envelope: `id` (`urn:uuid:<uuid>`), `realm`, `created_at`,
`updated_at`.

Two `$pkm.relations` shapes are valid:

1. **Verb map** (canonical typed relations, `relations.schema.json`):

```yaml
$pkm:
  id: "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
  realm: galley
  created_at: "2026-09-17T12:00:00Z"
  updated_at: "2026-09-17T12:00:00Z"
  relations:
    assignedToContact: "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000"
```

2. **Edge array** (harbormaster locker notes / older yeoman interaction form):

```yaml
$pkm:
  schema: $yeoman:interaction/v1
  relations:
    - target: "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000"
      type: contact
```

Harbormaster `graph_query._iter_relations` currently walks the **array** form
(or a top-level `relations` array). The verb-map form is the spec/fixture
contract used by `bosun-spec` graph tests. Optional envelope fields `schema`
and `urn` document the locker-note reconstruction path
(`urn:<realm>:<type>:<id>` from `$pkm.schema` + top-level `id`).

Marlinspike `patch_frontmatter` treats `$pkm` as an opaque YAML mapping and
does not re-validate the envelope.

---

## 5. Recipe provenance

Galley notes compose:

- Universal `$pkm` envelope (realm `galley`)
- Catalog dossier fields (`title`, `summary`, `tags`)
- Recipe body fields (`servings`, `prep_time_minutes`, `cook_time_minutes`,
  `total_time_minutes`, `ingredients_schema`)
- **Provenance** object aligned with
  [`canonical-note-contract-v0.1.json`](../schemas/canonical-note-contract-v0.1.json):
  `original_system`, `imported_at`, `converter_version`, `source_metadata`
- Optional schema.org `Recipe` block (`schema_org`)

Starter-vault example: [`examples/starter-vault/Recipes/skillet-beans.md`](../examples/starter-vault/Recipes/skillet-beans.md).

Marlinspike recipe surgery (`scale_recipe`, `scale_nutrition`, `convert_units`,
`reorder_steps`, `insert_step`) mutates `$recipe` / `$nutrition` / step lists
in place and does not rewrite provenance timestamps.

---

## 6. Query schema ownership

| Schema | Role | Implemented by |
|--------|------|----------------|
| `v1/query/graph-dsl.schema.json` | Full vault Graph DSL (filters, hops, projections) | `bosun-spec` `scripts/graph_query.py` tests |
| `v1/query/graph-neighborhood-query.schema.json` | Bounded `from` / `depth` / `direction` query | `harbormaster` `graph_query.py` |
| `v1/query/federated-query-plan.schema.json` | Full multi-vault plan (`vault_endpoints`, `join_keys`) | `bosun-spec` federated fixtures |
| `v1/query/federated-query-plan.runtime.schema.json` | `sites` + `queries` worker plan | `harbormaster` `federated_query.py` |

Harbormaster keeps local copies under `apps/harbormaster/schemas/v1/query/`
with the **runtime** `$id` values so they cannot collide with the full DSL
`$id`. See `harbormaster/apps/harbormaster/schemas/README.md`.
