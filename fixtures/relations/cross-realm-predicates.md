---
title: "Survey packet cited across the fleet"
status: active
tags:
  - drydock
  - squadron
  - docent
  - yeoman
created_at: "20260916200000"
updated_at: "20260916200000"
$pkm:
  relations:
    maintainedUnderLog:
      - "urn:drydock:maintenance:0d1e2f3a-4b5c-4d6e-8f70-890123456789"
    servicedInFleet:
      - "urn:squadron:service:1a2b3c4d-5e6f-4789-8abc-def012345678"
    citedInStudy:
      - "urn:docent:paper:9f8e7d6c-5b4a-4321-a098-76543210fedc"
    appraisedBy:
      - "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000"
---

# Survey packet cited across the fleet

Acid-test note for the expanded `$pkm.relations` predicate matrix. Each verb uses the conservative emit shape (a non-empty unique array of matching URNs):

- `maintainedUnderLog` → Drydock maintenance log
- `servicedInFleet` → Squadron service record
- `citedInStudy` → Docent paper
- `appraisedBy` → Yeoman contact
