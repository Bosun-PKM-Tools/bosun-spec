---
schema: "$trice:task/v1"
id: "01K5SAMPLETASK000000000000"
title: "Port Trice task-line markers"
state: "active"
project: "prj-schema-sync-01"
context:
  - "@computer"
priority: "high"
due: "2026-09-30"
scheduled: "2026-09-16"
tags:
  - trice
  - spec
blocked_by: []
created_at: "20260916090000"
updated_at: "20260916153000"
---

# Port Trice task-line markers

Standalone `$trice:task/v1` note. Inline `- [marker]` lines in any note body are parsed by the Trice task-line AST independently of this frontmatter contract.

The five strict bracket markers are: pending=` `, active=`/`, done=`x`, dropped=`-`, blocked=`!`.

- [ ] Pending: write the remaining fixture notes
- [/] Active: port the Trice schemas into bosun-spec
- [x] Done: inspect harbormaster `MARKER_TO_STATE`
- [-] Dropped: guess checkbox markers without reading the source
- [!] Blocked: waiting on Charthouse render review

## Nested children

- [ ] Parent checklist item
  - [ ] Two-space nested child, pending
  - [x] Two-space nested child, done
	- [/] Tab-indented nested child, active

Not a task line: `- [ ]` mentioned inside a sentence must not parse as a task.
- [z] unrecognized marker character is not one of the five states.
