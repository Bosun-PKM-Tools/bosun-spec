---
title: 'Strongbox Key: Master YubiKey Ed25519 Signing Key'
key_algorithm: Ed25519
public_key_fingerprint: SHA256:7f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3c
hardware_token_serial: YUBI-12345678
derivation_path: m/44'/60'/0'/0/0
$pkm:
  id: urn:uuid:01a0adb6-d2ea-712d-b2ac-bdd5a85733d5
  realm: strongbox
  created_at: '2026-09-16T12:00:00Z'
  updated_at: '2026-09-16T12:00:00Z'
  relations:
    assignedToContact: urn:yeoman:contact:0191fa30-1036-7000-8000-000000000036
---

# Strongbox Key: Master YubiKey Ed25519 Signing Key

Hardware cryptographic security token record storing master signing fingerprints.

## Cryptographic Parameters
Algorithm: `Ed25519` | Fingerprint: `SHA256:7f8a9b...` | Serial: `YUBI-12345678`

## Transcluded Key Topology
![[strongbox/keys/yubikey-primary#backup-matrix]]

## Security Envelope
Private scalar generated on-card; non-exportable hardware attestation confirmed.
^strongbox-master-key
