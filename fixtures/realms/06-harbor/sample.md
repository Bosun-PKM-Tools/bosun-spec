---
title: 'Harbor Ingress Route: Getting Started'
slug: getting-started
edge_route: /docs/intro
render_template: docs-page
$pkm:
  id: urn:uuid:01a0adb6-d2c3-71c6-b4cb-29e8987ce96a
  realm: harbor
  created_at: '2026-09-16T12:00:00Z'
  updated_at: '2026-09-16T12:00:00Z'
  relations:
    assignedToContact: urn:yeoman:contact:0191fa30-1006-7000-8000-000000000006
---

# Harbor Ingress Route: Getting Started

Edge router ingress mapping for documentation publication on the digital garden.

## Routing Parameters
Route: `/docs/intro`
Template: `docs-page`

## Transcluded Endpoint Mapping
![[harbor/routes/api-ingress#gateway-config]]

## Edge Ingress Policy
Static caching enabled with 300s TTL at the Cloudflare edge worker.
^harbor-ingress-docs
