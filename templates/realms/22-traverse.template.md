---
title: "{{ title }}"
geojson_feature:
  type: Feature
  geometry:
    type: Point
    coordinates:
    - 0.0
    - 0.0
  properties:
    name: Location Name
epsg_srid: 4326
survey_datum: "WGS84"
$pkm:
  id: "urn:uuid:{{ uuidv7 }}"
  realm: traverse
  created_at: "{{ date_utc }}"
  updated_at: "{{ date_utc }}"
  relations: {}
---

# {{ title }}

Spatial survey record holding RFC 7946 GeoJSON geographic features, coordinate systems, and survey datums.

## Geographic Overview

<!-- Starter notes and context for this section -->

## Coordinates & Spatial Spec

<!-- Starter notes and context for this section -->

## Field Survey Log

<!-- Starter notes and context for this section -->

## Boundary Notes

<!-- Starter notes and context for this section -->
