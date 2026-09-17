---
title: "Oil change assigned from the dock book"
status: active
tags:
  - drydock
  - yeoman
  - trice
created_at: "20260916190000"
updated_at: "20260916190000"
$pkm:
  relations:
    assignedToContact: "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000"
    maintainedUnderLog: "urn:drydock:maintenance:0d1e2f3a-4b5c-4d6e-8f70-890123456789"
---

# Oil change assigned from the dock book

Acid-test note showing Postel scalar URN acceptance: a single string where the conservative emit shape is a one-element array.

`assignedToContact` is an existing verb (Yeoman contact). `maintainedUnderLog` is a cross-realm Drydock maintenance verb. Runtime ingest MUST coerce each scalar to `["urn:..."]`; this schema only validates that both shapes are accepted.
