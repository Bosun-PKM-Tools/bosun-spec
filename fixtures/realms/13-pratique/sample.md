---
title: 'Pratique Health Telemetry: Polar H10 Cardio Session'
fhir_code: 8867-4
sensor_source: polar_h10_chest_strap
telemetry_parquet_ref: telemetry/pratique/heart_rate_20260916.parquet
$pkm:
  id: urn:uuid:01a0adb6-d2cc-7e34-ba7a-e4979466c6cd
  realm: pratique
  created_at: '2026-09-16T12:00:00Z'
  updated_at: '2026-09-16T12:00:00Z'
  relations:
    consultedProvider: urn:yeoman:contact:0191fa30-1013-7000-8000-000000000013
---

# Pratique Health Telemetry: Polar H10 Cardio Session

Biometric cardiovascular observation paired with local columnar Parquet dataset.

## Sensor & Clinical Code
Sensor: `polar_h10_chest_strap` | LOINC/FHIR: `8867-4` (Heart rate)

## Transcluded Biometrics
![[pratique/vitals/cardio-trends#hrv-analysis]]

## Analytical Summary
Mean resting heart rate recorded at 52 bpm with sympathetic tone equilibrium.
^pratique-hr-session
