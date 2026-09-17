---
title: 'Relay Escrow: Cryptographic Dead Man''s Switch'
dead_man_interval_days: 30
heartbeat_received_at: '2026-09-16T12:00:00Z'
master_recovery_key_cas: urn:relay:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43
$pkm:
  id: urn:uuid:01a0adb6-d2fb-7911-83fa-aa3028c88a15
  realm: relay
  created_at: '2026-09-16T12:00:00Z'
  updated_at: '2026-09-16T12:00:00Z'
  relations:
    waitingOnContact: urn:yeoman:contact:0191fa30-1050-7000-8000-000000000050
---

# Relay Escrow: Cryptographic Dead Man's Switch

Sovereign cryptographic dead man's switch monitor maintaining recovery escrow.

## Switch Configuration
Interval: 30 days | Last Heartbeat: `2026-09-16T12:00:00Z`

## Transcluded Protocol Spec
![[relay/protocols/continuity-plan#escrow-trustees]]

## Escrow Mechanism
Shamir secret shares distributed to three designated trustees upon heartbeat expiration.
^relay-continuity-switch
