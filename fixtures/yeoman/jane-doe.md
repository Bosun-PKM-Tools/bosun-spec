---
$pkm:
  schema: $yeoman:contact/v1
  relations: []
id: 550e8400-e29b-41d4-a716-446655440000
name: Jane Doe
emails:
  - jane.doe@example.org
  - jdoe@archive.example
channels:
  - kind: email
    value: jane.doe@example.org
    label: work
  - kind: email
    value: jdoe@archive.example
    label: archive
  - kind: phone
    value: "+1-555-0142"
    label: mobile
  - kind: matrix
    value: "@jane:example.org"
    label: chat
preferred_channel: email
---

# Jane Doe

Contact dossier for the local archive group. Yeoman reads this file from `locker_yeoman/contacts/<uuid>.md`.

## Channels

| Kind | Value | Label |
| --- | --- | --- |
| email | jane.doe@example.org | work |
| email | jdoe@archive.example | archive |
| phone | +1-555-0142 | mobile |
| matrix | @jane:example.org | chat |

Preferred channel: email.

## Notes

Met through the local archive group. Interactions are logged as `$yeoman:interaction/v1` notes that `$pkm.relations` back to this UUID with `type: contact`.
