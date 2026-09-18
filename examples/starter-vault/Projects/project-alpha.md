---
schema: "$trice:project/v1"
id: "prj-starter-alpha-01"
title: "Project Alpha — first vault loop"
status: active
author: Alex Rivera
area: "onboarding"
target_date: "2026-09-30"
tags:
  - project
  - onboarding
related_notes:
  - quickstart
  - skillet-beans
  - architecture-notes
task_count: 2
created_at: "20260917120000"
updated_at: "20260917120000"
$pkm:
  id: "urn:uuid:0191e5a0-1004-7000-8000-000000000004"
  realm: trice
  created_at: "2026-09-17T12:00:00Z"
  updated_at: "2026-09-17T12:00:00Z"
  relations:
    related:
      - "urn:uuid:0191e5a0-1001-7000-8000-000000000001"
      - "urn:uuid:0191e5a0-1002-7000-8000-000000000002"
      - "urn:uuid:0191e5a0-1003-7000-8000-000000000003"
---

# Project Alpha — first vault loop

Outcome: index this starter vault, query two properties, and run one Tender capture plus one Galley recipe capture.

`kikr find status:active` should hit this file (and any other note with `status: active`).

## Related notes

| Note | Link | Why it is on this project |
|------|------|---------------------------|
| Inbox walkthrough | [[quickstart]] | Tagged `onboarding`; first `kikr find` target |
| Recipe card | [[skillet-beans]] | Galley ingest sample |
| Architecture scratchpad | [[architecture-notes]] | CST checkboxes and `![[skillet-beans]]` transclusion |

## Scope

1. Run `kikr index` from `examples/starter-vault`.
2. Confirm `tag:onboarding` and `status:active` queries.
3. Capture `Inbox/` once with Tender.
4. Capture the skillet beans recipe text with `stax-chef`.

## Out of scope

Schema CI, KPP adapter work, and Charthouse worldbuilding.
