---
title: "Starter vault architecture notes"
tags:
  - architecture
  - cst
status: active
author: Alex Rivera
created_at: "20260917120000"
updated_at: "20260917120000"
related_notes:
  - skillet-beans
  - project-alpha
  - quickstart
$pkm:
  id: "urn:uuid:0191e5a0-1003-7000-8000-000000000003"
  realm: bosun
  created_at: "2026-09-17T12:00:00Z"
  updated_at: "2026-09-17T12:00:00Z"
  relations:
    related:
      - "urn:uuid:0191e5a0-1002-7000-8000-000000000002"
      - "urn:uuid:0191e5a0-1004-7000-8000-000000000004"
---

# Starter vault architecture notes

Scratchpad for how this vault is laid out. Notes stay Markdown on disk. Indexes under `.bosun/` are disposable.

Wikilinks use the note stem: [[skillet-beans]], [[project-alpha]], [[quickstart]]. Marlinspike and the graph query engine alias the file stem and the `*.md` filename.

## Layout

| Folder | Role |
|--------|------|
| `Inbox/` | Unsorted capture; Tender `capture-once` target |
| `Recipes/` | Galley Realm 12 recipe cards |
| `Notes/` | Working notes, CST task lines, transclusions |
| `Projects/` | Trice-style project briefs |

## CST task lines

Marlinspike toggles these in place. Pending is `- [ ]`; done is `- [x]`.

- [x] Confirm wikilink stems match filenames in this vault
- [ ] Re-index after adding a new Inbox note
- [ ] Ingest [[skillet-beans]] with `stax-chef capture-text`

## Transcluded recipe card

Embed of the skillet beans note (valid target in this vault):

![[skillet-beans]]

## Related project

See the active brief: [[project-alpha]].
