"""tests/test_telemetry_contracts.py
──────────────────────────────────
Unit test suite verifying:
  1. schemas/v1/telemetry/parquet-contracts.schema.json
     - Draft 2020-12 meta-schema compliance.
     - Canonical $id matching https://bosunpkm.com/schemas/v1/telemetry/parquet-contracts.schema.json.
  2. Conformance of generated Apache Parquet schema definitions and table contracts:
     - Realm 13 (Pratique): timestamp_utc (int64), metric_type (str), value (float64), unit (str), sensor_id (str).
     - Realm 16 (Squadron): timestamp_utc (int64), vin (str), engine_hours (float64), pid_code (str), raw_value (float64).
     - Realm 30 (The Glass): timestamp_utc (int64), station_id (str), barometric_hpa (float64), tidal_height_m (float64).
  3. Strict negative validation (type mismatches, missing fields, int64 overflow, negative engine hours).
  4. Physical unit conversion accuracy and registry conformance.

Usage:
  python tests/test_telemetry_contracts.py
  python -m pytest tests/test_telemetry_contracts.py -v
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
import unittest
from typing import Any, Dict

# Ensure repo root is on sys.path so scripts can be imported
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.telemetry_contracts import (
    PRATIQUE_COLUMNS,
    REALM_COLUMNS,
    SQUADRON_COLUMNS,
    THE_GLASS_COLUMNS,
    UNIT_CONVERSIONS,
    convert_unit,
    generate_parquet_schema_definition,
    generate_parquet_table_contract,
    generate_sample_batch,
    generate_sample_record,
    generate_telemetry_catalog,
)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "telemetry" / "parquet-contracts.schema.json"
_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID = "https://bosunpkm.com/schemas/v1/telemetry/parquet-contracts.schema.json"


class TestTelemetryContracts(unittest.TestCase):
    """Test suite validating Parquet schema contracts and unit conversions."""

    @classmethod
    def setUpClass(cls):
        if not _SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Telemetry schema not found at {_SCHEMA_PATH}")
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            cls.schema_json = json.load(fh)
        if _HAS_JSONSCHEMA:
            Draft202012Validator.check_schema(cls.schema_json)
            cls.validator = Draft202012Validator(cls.schema_json)

    # -----------------------------------------------------------------------
    # Schema Metadata and Structural Tests
    # -----------------------------------------------------------------------

    def test_schema_file_exists_and_parses_json(self):
        """Schema file must exist and parse as valid JSON dictionary."""
        self.assertTrue(_SCHEMA_PATH.is_file())
        self.assertIsInstance(self.schema_json, dict)

    def test_schema_declares_draft_2020_12(self):
        """Schema must pin JSON Schema Draft 2020-12."""
        self.assertEqual(self.schema_json.get("$schema"), _DRAFT_2020_12)

    def test_schema_declares_canonical_id(self):
        """Schema must declare canonical $id matching path."""
        self.assertEqual(self.schema_json.get("$id"), _CANONICAL_ID)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_schema_passes_meta_schema_check(self):
        """Schema itself must satisfy the Draft 2020-12 meta-schema."""
        Draft202012Validator.check_schema(self.schema_json)

    # -----------------------------------------------------------------------
    # Generated Parquet Schema Definitions Conformance
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_generated_pratique_schema_definition_conforms(self):
        """Pratique generated Parquet schema definition conforms to contract."""
        schema_def = generate_parquet_schema_definition("pratique")
        self.validator.validate(schema_def)

        # Explicitly verify required fields and types
        field_names = [f["name"] for f in schema_def["fields"]]
        expected_fields = ["timestamp_utc", "metric_type", "value", "unit", "sensor_id"]
        self.assertEqual(field_names, expected_fields)

        field_map = {f["name"]: f for f in schema_def["fields"]}
        self.assertEqual(field_map["timestamp_utc"]["type"], "INT64")
        self.assertEqual(field_map["metric_type"]["type"], "STRING")
        self.assertEqual(field_map["value"]["type"], "DOUBLE")
        self.assertEqual(field_map["unit"]["type"], "STRING")
        self.assertEqual(field_map["sensor_id"]["type"], "STRING")

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_generated_squadron_schema_definition_conforms(self):
        """Squadron generated Parquet schema definition conforms to contract."""
        schema_def = generate_parquet_schema_definition("squadron")
        self.validator.validate(schema_def)

        # Explicitly verify required fields and types
        field_names = [f["name"] for f in schema_def["fields"]]
        expected_fields = ["timestamp_utc", "vin", "engine_hours", "pid_code", "raw_value"]
        self.assertEqual(field_names, expected_fields)

        field_map = {f["name"]: f for f in schema_def["fields"]}
        self.assertEqual(field_map["timestamp_utc"]["type"], "INT64")
        self.assertEqual(field_map["vin"]["type"], "STRING")
        self.assertEqual(field_map["engine_hours"]["type"], "DOUBLE")
        self.assertEqual(field_map["pid_code"]["type"], "STRING")
        self.assertEqual(field_map["raw_value"]["type"], "DOUBLE")

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_generated_the_glass_schema_definition_conforms(self):
        """The Glass generated Parquet schema definition conforms to contract."""
        schema_def = generate_parquet_schema_definition("the_glass")
        self.validator.validate(schema_def)

        # Explicitly verify required fields and types
        field_names = [f["name"] for f in schema_def["fields"]]
        expected_fields = ["timestamp_utc", "station_id", "barometric_hpa", "tidal_height_m"]
        self.assertEqual(field_names, expected_fields)

        field_map = {f["name"]: f for f in schema_def["fields"]}
        self.assertEqual(field_map["timestamp_utc"]["type"], "INT64")
        self.assertEqual(field_map["station_id"]["type"], "STRING")
        self.assertEqual(field_map["barometric_hpa"]["type"], "DOUBLE")
        self.assertEqual(field_map["tidal_height_m"]["type"], "DOUBLE")

    # -----------------------------------------------------------------------
    # Table Contract and Catalog Conformance
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_generated_table_contracts_conform(self):
        """Generated table contracts for all 3 realms conform to parquet-contracts."""
        for realm in ("pratique", "squadron", "the_glass"):
            with self.subTest(realm=realm):
                tc = generate_parquet_table_contract(realm)
                self.validator.validate(tc)
                self.assertEqual(tc["primary_key"], "timestamp_utc")
                self.assertTrue(len(tc["columns"]) >= 4)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_generated_telemetry_catalog_conforms(self):
        """Full fleet telemetry catalog conforms to parquet-contracts."""
        catalog = generate_telemetry_catalog()
        self.validator.validate(catalog)
        self.assertEqual(catalog["archetype"], "dual-track-telemetry")
        self.assertIn("pratique", catalog["contracts"])
        self.assertIn("squadron", catalog["contracts"])
        self.assertIn("the_glass", catalog["contracts"])
        self.assertGreater(len(catalog["unit_conversions"]), 10)

    # -----------------------------------------------------------------------
    # Row Record Validation (Positive Cases)
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_valid_pratique_records(self):
        """Valid Pratique observation rows validate cleanly."""
        records = [
            {
                "timestamp_utc": 1726588800000000,
                "metric_type": "heart_rate",
                "value": 72.0,
                "unit": "bpm",
                "sensor_id": "sensor-polar-h10-01",
            },
            {
                "timestamp_utc": 1726588801000000,
                "metric_type": "spo2",
                "value": 98.5,
                "unit": "%",
                "sensor_id": "sensor-masimo-pulseox-02",
            },
            {
                "timestamp_utc": 1726588802000000,
                "metric_type": "blood_glucose",
                "value": 5.4,
                "unit": "mmol/L",
                "sensor_id": "sensor-dexcom-g7-01",
            },
        ]
        for rec in records:
            with self.subTest(metric=rec["metric_type"]):
                self.validator.validate(rec)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_valid_squadron_records(self):
        """Valid Squadron vehicular telemetry rows validate cleanly."""
        records = [
            {
                "timestamp_utc": 1726588800000000,
                "vin": "1HGCR2F83HA000000",
                "engine_hours": 142.5,
                "pid_code": "010C",
                "raw_value": 2400.0,
            },
            {
                "timestamp_utc": 1726588801000000,
                "vin": "1HGCR2F83HA000000",
                "engine_hours": 142.5,
                "pid_code": "010D",
                "raw_value": 65.0,
            },
            {
                "timestamp_utc": 1726588802000000,
                "vin": "1HGCR2F83HA000000",
                "engine_hours": 0.0,
                "pid_code": "0105",
                "raw_value": 88.0,
            },
        ]
        for rec in records:
            with self.subTest(pid=rec["pid_code"]):
                self.validator.validate(rec)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_valid_the_glass_records(self):
        """Valid The Glass meteorological rows validate cleanly."""
        records = [
            {
                "timestamp_utc": 1726588800000000,
                "station_id": "buoy-station-44013",
                "barometric_hpa": 1013.25,
                "tidal_height_m": 2.45,
            },
            {
                "timestamp_utc": 1726588860000000,
                "station_id": "buoy-station-44013",
                "barometric_hpa": 1012.80,
                "tidal_height_m": 2.61,
            },
            {
                "timestamp_utc": 1726588920000000,
                "station_id": "tide-sensor-boston-harbor",
                "barometric_hpa": 1014.10,
                "tidal_height_m": -0.35,
            },
        ]
        for rec in records:
            with self.subTest(station=rec["station_id"]):
                self.validator.validate(rec)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_valid_record_batch_envelope(self):
        """recordBatch envelopes with multiple items validate cleanly."""
        for realm in ("pratique", "squadron", "the_glass"):
            with self.subTest(realm=realm):
                batch = generate_sample_batch(realm, count=3)
                self.validator.validate(batch)

    # -----------------------------------------------------------------------
    # Negative Validation Tests
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_invalid_record_rejected_for_string_timestamp(self):
        """Record with string timestamp (instead of int64) must be rejected."""
        rec = generate_sample_record("pratique", timestamp_utc="2026-09-17T12:00:00Z")
        with self.assertRaises(ValidationError):
            self.validator.validate(rec)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_invalid_record_rejected_for_float_timestamp(self):
        """Record with float timestamp (instead of int64) must be rejected."""
        rec = generate_sample_record("the_glass", timestamp_utc=1726588800.5)
        with self.assertRaises(ValidationError):
            self.validator.validate(rec)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_invalid_record_rejected_for_int64_overflow(self):
        """Record with timestamp exceeding signed 64-bit int bound must be rejected."""
        rec = generate_sample_record("squadron", timestamp_utc=9223372036854775808)
        with self.assertRaises(ValidationError):
            self.validator.validate(rec)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_invalid_record_rejected_for_missing_required_fields(self):
        """Record missing required domain attributes must be rejected."""
        # Pratique missing sensor_id
        rec_pratique = {
            "timestamp_utc": 1726588800000000,
            "metric_type": "heart_rate",
            "value": 72.0,
            "unit": "bpm",
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(rec_pratique)

        # Squadron missing vin
        rec_squadron = {
            "timestamp_utc": 1726588800000000,
            "engine_hours": 10.0,
            "pid_code": "010C",
            "raw_value": 2000.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(rec_squadron)

        # The Glass missing barometric_hpa
        rec_glass = {
            "timestamp_utc": 1726588800000000,
            "station_id": "buoy-01",
            "tidal_height_m": 1.2,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(rec_glass)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_squadron_negative_engine_hours_rejected(self):
        """Squadron record with negative engine_hours must be rejected."""
        rec = generate_sample_record("squadron", engine_hours=-1.0)
        with self.assertRaises(ValidationError):
            self.validator.validate(rec)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_invalid_type_in_scalar_value_rejected(self):
        """String value in float64 field must be rejected."""
        rec = generate_sample_record("pratique", value="seventy-two")
        with self.assertRaises(ValidationError):
            self.validator.validate(rec)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_additional_properties_rejected_in_records(self):
        """Unrecognized extraneous attributes must be rejected."""
        rec = generate_sample_record("the_glass", unexpected_field="malicious_payload")
        with self.assertRaises(ValidationError):
            self.validator.validate(rec)

    # -----------------------------------------------------------------------
    # Unit Conversions Tests
    # -----------------------------------------------------------------------

    def test_unit_conversion_barometric_pressure_inhg_to_hpa(self):
        """29.92 inHg converts to ~1013.208 hPa."""
        hpa = convert_unit(29.92, "inHg", "hPa")
        self.assertAlmostEqual(hpa, 1013.2075, places=3)

    def test_unit_conversion_blood_pressure_mmhg_to_hpa(self):
        """120 mmHg converts to ~159.987 hPa."""
        hpa = convert_unit(120.0, "mmHg", "hPa")
        self.assertAlmostEqual(hpa, 159.9868, places=3)

    def test_unit_conversion_pressure_psi_to_kpa(self):
        """32.0 psi converts to ~220.632 kPa."""
        kpa = convert_unit(32.0, "psi", "kPa")
        self.assertAlmostEqual(kpa, 220.6322, places=3)

    def test_unit_conversion_speed_mph_to_kmh(self):
        """60.0 mph converts to 96.56064 km/h."""
        kmh = convert_unit(60.0, "mph", "km/h")
        self.assertAlmostEqual(kmh, 96.56064, places=4)

    def test_unit_conversion_speed_knots_to_ms(self):
        """10.0 knots converts to ~5.144 m/s."""
        ms = convert_unit(10.0, "knots", "m/s")
        self.assertAlmostEqual(ms, 5.14444, places=4)

    def test_unit_conversion_temperature_degf_to_degc(self):
        """Fahrenheit to Celsius conversion handles freezing, boiling, and normal body temp."""
        self.assertAlmostEqual(convert_unit(32.0, "degF", "degC"), 0.0, places=5)
        self.assertAlmostEqual(convert_unit(212.0, "degF", "degC"), 100.0, places=5)
        self.assertAlmostEqual(convert_unit(98.6, "degF", "degC"), 37.0, places=4)

    def test_unit_conversion_temperature_degc_to_degf(self):
        """Celsius to Fahrenheit conversion round-trips cleanly."""
        self.assertAlmostEqual(convert_unit(0.0, "degC", "degF"), 32.0, places=5)
        self.assertAlmostEqual(convert_unit(100.0, "degC", "degF"), 212.0, places=5)
        self.assertAlmostEqual(convert_unit(37.0, "degC", "degF"), 98.6, places=4)

    def test_unit_conversion_length_ft_to_m(self):
        """Tidal height in feet converts to meters (10 ft = 3.048 m)."""
        m = convert_unit(10.0, "ft", "m")
        self.assertAlmostEqual(m, 3.048, places=4)

    def test_unit_conversion_clinical_blood_glucose(self):
        """Blood glucose 90.0 mg/dL converts to ~4.995 mmol/L."""
        mmol = convert_unit(90.0, "mg/dL", "mmol/L")
        self.assertAlmostEqual(mmol, 4.9949, places=3)
        mgdl = convert_unit(mmol, "mmol/L", "mg/dL")
        self.assertAlmostEqual(mgdl, 90.0, places=3)

    def test_unit_conversion_volume_gal_to_l(self):
        """Fuel volume 15.0 gal converts to ~56.78 L."""
        liters = convert_unit(15.0, "gal", "L")
        self.assertAlmostEqual(liters, 56.78117, places=4)

    def test_unit_conversion_identity(self):
        """Same unit conversion returns identity value."""
        self.assertEqual(convert_unit(42.5, "hPa", "hPa"), 42.5)
        self.assertEqual(convert_unit(100.0, "bpm", "bpm"), 100.0)

    def test_unit_conversion_unregistered_raises_value_error(self):
        """Unregistered unit conversion must raise ValueError."""
        with self.assertRaises(ValueError):
            convert_unit(100.0, "parsecs", "lightyears")

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_all_unit_conversion_entries_satisfy_schema(self):
        """All entries in UNIT_CONVERSIONS registry conform to #/$defs/unitConversion."""
        subvalidator = Draft202012Validator(self.schema_json["$defs"]["unitConversion"])
        for rule in UNIT_CONVERSIONS:
            with self.subTest(rule=f"{rule['source_unit']}->{rule['target_unit']}"):
                subvalidator.validate(rule)


if __name__ == "__main__":
    unittest.main()
