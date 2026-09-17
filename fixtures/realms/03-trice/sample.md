---
title: Audit Cryptographic Signatures Across Fleet Matrices
task_state: active
priority: p1
recurrence_rule: FREQ=WEEKLY;BYDAY=MO
$pkm:
  id: urn:uuid:01a0adb6-d2be-7457-be8c-c607b0b18fd1
  realm: trice
  created_at: '2026-09-16T12:00:00Z'
  updated_at: '2026-09-16T12:00:00Z'
  relations:
    actionItemDerivedFrom: urn:trice:task:0191fa30-1003-7000-8000-000000000003
---

# Audit Cryptographic Signatures Across Fleet Matrices

Action item to perform weekly verification of JSON-RPC matrix endpoint signatures.

## Task Execution
Iterate through all vessel definitions and verify Ed25519 signatures on RPC headers.

## Transcluded Requirements
![[trice/projects/spec-synchronization#deliverables]]

## Status Tracking
- State: `active`
- Priority: `p1`
- Recurrence: `FREQ=WEEKLY;BYDAY=MO`
^trice-audit-sig
