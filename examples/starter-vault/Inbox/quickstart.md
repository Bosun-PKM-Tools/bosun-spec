---
title: "Starter vault walkthrough"
tags:
  - onboarding
  - inbox
status: inbox
author: Alex Rivera
created_at: "20260917120000"
updated_at: "20260917120000"
$pkm:
  id: "urn:uuid:0191e5a0-1001-7000-8000-000000000001"
  realm: harbor
  created_at: "2026-09-17T12:00:00Z"
  updated_at: "2026-09-17T12:00:00Z"
  relations:
    related:
      - "urn:uuid:0191e5a0-1002-7000-8000-000000000002"
      - "urn:uuid:0191e5a0-1003-7000-8000-000000000003"
      - "urn:uuid:0191e5a0-1004-7000-8000-000000000004"
---

# Starter vault walkthrough

Drop-inbox note for first-run indexing. After `kikr index` from this vault root, `kikr find tag:onboarding` should return this file.

Related notes in this vault:

- Recipe card: [[skillet-beans]]
- Architecture scratchpad (tasks + transclusion): [[architecture-notes]]
- Active project brief: [[project-alpha]]

Capture more files into `Inbox/` and re-run `kikr index`. Tender can also sweep this folder with `tender-watch --vault . capture-once --path Inbox`.
