---
schema: "$trice:task/v1"
id: "01K5DELEGATEDTASK0000000000"
title: "Follow up with Jane on the archive ingest"
state: "blocked"
project: "prj-schema-sync-01"
context:
  - "@waiting"
priority: "high"
due: "2026-09-23"
scheduled: "2026-09-16"
tags:
  - trice
  - yeoman
blocked_by: []
created_at: "20260916120000"
updated_at: "20260916154500"
$pkm:
  relations:
    assignedToContact: "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000"
---

# Follow up with Jane on the archive ingest

Standalone `$trice:task/v1` action assigned to a Yeoman contact through the typed `$pkm.relations` object.

The predicate `assignedToContact` MUST target a canonical contact URN:

`urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000`

That UUID matches the Jane Doe dossier fixture (`fixtures/yeoman/jane-doe.md`) and the harbormaster method-matrix contact id.

- [!] Blocked: waiting on Jane to confirm the locker path
- [ ] Send Jane the ingest checklist after she replies
