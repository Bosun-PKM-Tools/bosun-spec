# User #1 Quick Start (5 Minutes)

Index the starter vault, query two properties, then run one Tender capture and one Galley recipe capture. Commands below are the same on Windows PowerShell and Unix shells unless a PowerShell variant is shown.

Assume this fleet is cloned as siblings (the layout used in local development):

```text
<repos>/bosun-spec
<repos>/harbormaster
<repos>/tender
<repos>/galley
<repos>/marlinspike
```

Run install from `bosun-spec`. After that, `cd` into `examples/starter-vault` for index, find, and ingest.

## 1. Prerequisites

- **Python 3.11+** (harbormaster, tender, and galley all require 3.11)
- **Marlinspike** as either:
  - a pre-compiled `marlinspike` binary on `PATH` (`marlinspike.exe` on Windows), or
  - a Rust stable toolchain (`cargo`) so you can build it

Marlinspike is not published on crates.io. Until a GitHub release binary is on `PATH`, build from the sibling repo:

```bash
cargo build --release -p marlinspike-cli -p marlinspike-kpp
```

Binaries land at `marlinspike/target/release/marlinspike` (`.exe` on Windows) and `marlinspike-kpp`.

Python packages in this fleet are **not** published to PyPI. Install them editable from the local clones (next step).

## 2. Install the toolchain

From `bosun-spec`:

```bash
python -m pip install -e ../harbormaster/apps/harbormaster -e ../tender/apps/tender -e ../galley/apps/galley
```

That one line registers:

| Script | Package path | What you get |
|--------|----------------|--------------|
| `kikr`, `harbormaster` | `harbormaster/apps/harbormaster` | YAML property index + event bus |
| `tender`, `tender-watch`, `tender-kpp` | `tender/apps/tender` | Capture daemon + folder ingest |
| `stax-chef` | `galley/apps/galley` | Recipe capture (Galley engine) |

Absolute equivalent on this machine:

```bash
python -m pip install -e C:\dev\repos\harbormaster\apps\harbormaster -e C:\dev\repos\tender\apps\tender -e C:\dev\repos\galley\apps\galley
```

Confirm the scripts resolve:

```bash
kikr --help
tender-watch --help
stax-chef --help
```

## 3. Index the starter vault

`kikr` has no `--vault` flag. It delta-scans the **current working directory** (workspace name `workspace`) and writes `.bosun/kikr_index.db`.

```bash
cd examples/starter-vault
kikr index
```

Stay in `examples/starter-vault` for the rest of this guide so find queries read the same index.

## 4. Query knowledge graph properties

`kikr find` accepts `key:value` (substring match on the value) or free text. Tags in frontmatter are stored under the key `tag`.

```bash
kikr find tag:onboarding
kikr find status:active
```

Expected hits in this vault:

| Query | Matches |
|-------|---------|
| `tag:onboarding` | `Inbox/quickstart.md`, `Projects/project-alpha.md` |
| `status:active` | `Projects/project-alpha.md`, `Notes/architecture-notes.md`, `Recipes/skillet-beans.md` |

`Inbox/quickstart.md` uses `status: inbox`, so it should not appear in `status:active`.

## 5. Ingest content (Tender + Galley)

Still from `examples/starter-vault`.

### Tender — capture the Inbox folder

Folder ingest is `tender-watch capture-once` (console script from `tender.cli`). `--path` is a **directory** of `.md` / `.txt` files, not a single file.

```bash
tender-watch --vault . capture-once --path Inbox
```

That reads `Inbox/quickstart.md` into the vault capture path and graph index. Keyword recall afterward:

```bash
tender-watch --vault . recall onboarding
```

### Galley — capture the skillet beans recipe

Galley ingest is `stax-chef capture-text` (there is no `galley ingest` command and no markdown-path subcommand). Pass the recipe body as text and set `--source-uri` so provenance points at the starter file.

PowerShell:

```powershell
stax-chef init-db --db .\stax_chef.db
stax-chef capture-text (Get-Content -Raw .\Recipes\skillet-beans.md) --source-uri "file:Recipes/skillet-beans.md" --db .\stax_chef.db
```

Unix:

```bash
stax-chef init-db --db ./stax_chef.db
stax-chef capture-text "$(cat Recipes/skillet-beans.md)" --source-uri "file:Recipes/skillet-beans.md" --db ./stax_chef.db
```

`stax-chef.db` is local SQLite (default `./stax_chef.db`). It is gitignored at the spec-repo root as `*.db`; do not commit it.

Optional KPP fetch (needs `galley-kpp` or `python src/galley/rpc_server.py` running, plus `harbormaster` on `PATH`):

```bash
harbormaster galley recipe Recipes/skillet-beans.md
```

That calls `galley.get_recipe` with the path string. It is a lookup, not the capture pipeline above.

## Vault map

| Path | What it demonstrates |
|------|----------------------|
| `Inbox/quickstart.md` | YAML `title` / `tags` / `status` / `author`; `tag: onboarding`; wikilinks `[[skillet-beans]]`, `[[architecture-notes]]`, `[[project-alpha]]` |
| `Recipes/skillet-beans.md` | Galley Realm 12 `ingredients_schema`, `$pkm`, schema.org Recipe, provenance `source` / `author` / `date` |
| `Notes/architecture-notes.md` | CST `- [ ]` / `- [x]` and transclusion `![[skillet-beans]]` |
| `Projects/project-alpha.md` | `status: active`, `related_notes`, `$pkm.relations` |

Wikilinks are `[[stem]]` (file stem, optional `[[stem\|label]]` or `[[stem#heading]]`). Transclusions are `![[stem]]`.
