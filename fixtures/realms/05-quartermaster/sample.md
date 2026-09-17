---
title: 'Operating Treasury Ledger: Checking Account'
beancount_account: Assets:Bank:Checking
tx_hash: tx_abc123def4567890
currency_code: USD
$pkm:
  id: urn:uuid:01a0adb6-d2c1-702d-ac89-edbd233a62fb
  realm: quartermaster
  created_at: '2026-09-16T12:00:00Z'
  updated_at: '2026-09-16T12:00:00Z'
  relations:
    purchasedViaTx: urn:qtm:tx:0191fa30-1005-7000-8000-000000000005
---

# Operating Treasury Ledger: Checking Account

Double-entry plain-text accounting transaction dossier for operational treasury disbursements.

## Ledger Account Spec
Account: `Assets:Bank:Checking`
Tx Hash: `tx_abc123def4567890`

## Transcluded Records
![[quartermaster/ledgers/2026-q3#operating-expenses]]

## Reconciliation Audit
Matched against monthly banking clearinghouse statement with zero variance.
^qtm-checking-ledger
