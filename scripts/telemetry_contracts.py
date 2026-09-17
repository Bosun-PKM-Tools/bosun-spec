"""scripts/telemetry_contracts.py
──────────────────────────────
Apache Parquet Schema Definitions & Unit Conversions for Archetype 3 Realms.

Defines columnar schemas and unit conversions for:
  - Realm 13 (Pratique): Clinical biometrics and HL7 vitals.
  - Realm 16 (Squadron): Vehicular OBD-II / CAN-bus telemetry.
  - Realm 30 (The Glass): Meteorological and tidal sensor observations.

Provides utilities to generate Parquet table contracts, schema definitions,
catalog manifests, and perform physical unit conversions conforming to:
  schemas/v1/telemetry/parquet-contracts.schema.json

Usage:
  python scripts/telemetry_contracts.py --help
  python scripts/telemetry_contracts.py --catalog
  python scripts/telemetry_contracts.py --verify
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "telemetry" / "parquet-contracts.schema.json"

# ---------------------------------------------------------------------------
# Archetype 3 Column Specifications
# ---------------------------------------------------------------------------

PRATIQUE_COLUMNS: List[Dict[str, Any]] = [
    {
        "name": "timestamp_utc",
        "type": "INT64",
        "logical_type": "TIMESTAMP_MICROS",
        "nullable": False,
        "unit": "microseconds",
        "description": "UTC timestamp in microseconds since Unix epoch.",
    },
    {
        "name": "metric_type",
        "type": "STRING",
        "logical_type": "UTF8",
        "nullable": False,
        "unit": "dimensionless",
        "description": "Biometric metric identifier (e.g. heart_rate, spo2, systolic_bp, blood_glucose).",
    },
    {
        "name": "value",
        "type": "DOUBLE",
        "logical_type": "NONE",
        "nullable": False,
        "description": "Observed clinical measurement value as float64 / DOUBLE.",
    },
    {
        "name": "unit",
        "type": "STRING",
        "logical_type": "UTF8",
        "nullable": False,
        "description": "Measurement unit string (e.g. bpm, %, mmHg, mg/dL, degC).",
    },
    {
        "name": "sensor_id",
        "type": "STRING",
        "logical_type": "UTF8",
        "nullable": False,
        "description": "Identifier of the medical device or clinical sensor source.",
    },
]

SQUADRON_COLUMNS: List[Dict[str, Any]] = [
    {
        "name": "timestamp_utc",
        "type": "INT64",
        "logical_type": "TIMESTAMP_MICROS",
        "nullable": False,
        "unit": "microseconds",
        "description": "UTC timestamp in microseconds since Unix epoch.",
    },
    {
        "name": "vin",
        "type": "STRING",
        "logical_type": "UTF8",
        "nullable": False,
        "description": "17-character ISO 3779 Vehicle Identification Number or fleet vessel ID.",
    },
    {
        "name": "engine_hours",
        "type": "DOUBLE",
        "logical_type": "NONE",
        "nullable": False,
        "unit": "hours",
        "description": "Accumulated vehicle or vessel engine operational hours.",
    },
    {
        "name": "pid_code",
        "type": "STRING",
        "logical_type": "UTF8",
        "nullable": False,
        "description": "OBD-II Parameter ID (e.g. 010C for RPM, 010D for Speed) or CAN-bus message code.",
    },
    {
        "name": "raw_value",
        "type": "DOUBLE",
        "logical_type": "NONE",
        "nullable": False,
        "description": "Raw scalar telemetry reading as float64 / DOUBLE.",
    },
]

THE_GLASS_COLUMNS: List[Dict[str, Any]] = [
    {
        "name": "timestamp_utc",
        "type": "INT64",
        "logical_type": "TIMESTAMP_MICROS",
        "nullable": False,
        "unit": "microseconds",
        "description": "UTC timestamp in microseconds since Unix epoch.",
    },
    {
        "name": "station_id",
        "type": "STRING",
        "logical_type": "UTF8",
        "nullable": False,
        "description": "Meteorological weather station, buoy, or barometer identifier.",
    },
    {
        "name": "barometric_hpa",
        "type": "DOUBLE",
        "logical_type": "NONE",
        "nullable": False,
        "unit": "hPa",
        "description": "Atmospheric barometric pressure in hectopascals (hPa).",
    },
    {
        "name": "tidal_height_m",
        "type": "DOUBLE",
        "logical_type": "NONE",
        "nullable": False,
        "unit": "m",
        "description": "Observed tidal water level or sea surface height in meters.",
    },
]

REALM_COLUMNS: Dict[str, List[Dict[str, Any]]] = {
    "pratique": PRATIQUE_COLUMNS,
    "13-pratique": PRATIQUE_COLUMNS,
    "squadron": SQUADRON_COLUMNS,
    "16-squadron": SQUADRON_COLUMNS,
    "the_glass": THE_GLASS_COLUMNS,
    "the-glass": THE_GLASS_COLUMNS,
    "30-the-glass": THE_GLASS_COLUMNS,
}

# ---------------------------------------------------------------------------
# Unit Conversions Registry
# ---------------------------------------------------------------------------

UNIT_CONVERSIONS: List[Dict[str, Any]] = [
    # Meteorological / Pressure (The Glass & Pratique)
    {
        "source_unit": "inHg",
        "target_unit": "hPa",
        "factor": 33.863886666667,
        "offset": 0.0,
        "formula": "hPa = inHg * 33.863886666667",
        "dimension": "pressure",
        "realm": "the_glass",
    },
    {
        "source_unit": "hPa",
        "target_unit": "inHg",
        "factor": 1.0 / 33.863886666667,
        "offset": 0.0,
        "formula": "inHg = hPa / 33.863886666667",
        "dimension": "pressure",
        "realm": "the_glass",
    },
    {
        "source_unit": "mmHg",
        "target_unit": "hPa",
        "factor": 1.33322387415,
        "offset": 0.0,
        "formula": "hPa = mmHg * 1.33322387415",
        "dimension": "pressure",
        "realm": "pratique",
    },
    {
        "source_unit": "hPa",
        "target_unit": "mmHg",
        "factor": 1.0 / 1.33322387415,
        "offset": 0.0,
        "formula": "mmHg = hPa / 1.33322387415",
        "dimension": "pressure",
        "realm": "pratique",
    },
    {
        "source_unit": "psi",
        "target_unit": "kPa",
        "factor": 6.894757293168,
        "offset": 0.0,
        "formula": "kPa = psi * 6.894757293168",
        "dimension": "pressure",
        "realm": "squadron",
    },
    {
        "source_unit": "kPa",
        "target_unit": "psi",
        "factor": 1.0 / 6.894757293168,
        "offset": 0.0,
        "formula": "psi = kPa / 6.894757293168",
        "dimension": "pressure",
        "realm": "squadron",
    },
    {
        "source_unit": "bar",
        "target_unit": "hPa",
        "factor": 1000.0,
        "offset": 0.0,
        "formula": "hPa = bar * 1000",
        "dimension": "pressure",
        "realm": "global",
    },
    # Length / Tidal height
    {
        "source_unit": "ft",
        "target_unit": "m",
        "factor": 0.3048,
        "offset": 0.0,
        "formula": "m = ft * 0.3048",
        "dimension": "length",
        "realm": "the_glass",
    },
    {
        "source_unit": "m",
        "target_unit": "ft",
        "factor": 1.0 / 0.3048,
        "offset": 0.0,
        "formula": "ft = m / 0.3048",
        "dimension": "length",
        "realm": "the_glass",
    },
    {
        "source_unit": "in",
        "target_unit": "cm",
        "factor": 2.54,
        "offset": 0.0,
        "formula": "cm = in * 2.54",
        "dimension": "length",
        "realm": "global",
    },
    {
        "source_unit": "cm",
        "target_unit": "in",
        "factor": 1.0 / 2.54,
        "offset": 0.0,
        "formula": "in = cm / 2.54",
        "dimension": "length",
        "realm": "global",
    },
    {
        "source_unit": "in",
        "target_unit": "mm",
        "factor": 25.4,
        "offset": 0.0,
        "formula": "mm = in * 25.4",
        "dimension": "length",
        "realm": "global",
    },
    # Velocity / Speed
    {
        "source_unit": "mph",
        "target_unit": "km/h",
        "factor": 1.609344,
        "offset": 0.0,
        "formula": "km/h = mph * 1.609344",
        "dimension": "speed",
        "realm": "squadron",
    },
    {
        "source_unit": "km/h",
        "target_unit": "mph",
        "factor": 1.0 / 1.609344,
        "offset": 0.0,
        "formula": "mph = km/h / 1.609344",
        "dimension": "speed",
        "realm": "squadron",
    },
    {
        "source_unit": "knots",
        "target_unit": "m/s",
        "factor": 0.514444444444,
        "offset": 0.0,
        "formula": "m/s = knots * 0.514444444444",
        "dimension": "speed",
        "realm": "the_glass",
    },
    {
        "source_unit": "m/s",
        "target_unit": "knots",
        "factor": 1.0 / 0.514444444444,
        "offset": 0.0,
        "formula": "knots = m/s / 0.514444444444",
        "dimension": "speed",
        "realm": "the_glass",
    },
    {
        "source_unit": "knots",
        "target_unit": "km/h",
        "factor": 1.852,
        "offset": 0.0,
        "formula": "km/h = knots * 1.852",
        "dimension": "speed",
        "realm": "the_glass",
    },
    # Temperature
    {
        "source_unit": "degF",
        "target_unit": "degC",
        "factor": 5.0 / 9.0,
        "offset": -32.0,
        "formula": "degC = (degF - 32) * 5 / 9",
        "dimension": "temperature",
        "realm": "global",
    },
    {
        "source_unit": "degC",
        "target_unit": "degF",
        "factor": 9.0 / 5.0,
        "offset": 32.0,
        "formula": "degF = (degC * 9 / 5) + 32",
        "dimension": "temperature",
        "realm": "global",
    },
    # Volume
    {
        "source_unit": "gal",
        "target_unit": "L",
        "factor": 3.785411784,
        "offset": 0.0,
        "formula": "L = gal * 3.785411784",
        "dimension": "volume",
        "realm": "squadron",
    },
    {
        "source_unit": "L",
        "target_unit": "gal",
        "factor": 1.0 / 3.785411784,
        "offset": 0.0,
        "formula": "gal = L / 3.785411784",
        "dimension": "volume",
        "realm": "squadron",
    },
    # Mass
    {
        "source_unit": "lbs",
        "target_unit": "kg",
        "factor": 0.45359237,
        "offset": 0.0,
        "formula": "kg = lbs * 0.45359237",
        "dimension": "mass",
        "realm": "pratique",
    },
    {
        "source_unit": "kg",
        "target_unit": "lbs",
        "factor": 1.0 / 0.45359237,
        "offset": 0.0,
        "formula": "lbs = kg / 0.45359237",
        "dimension": "mass",
        "realm": "pratique",
    },
    # Clinical Concentration (Blood Glucose)
    {
        "source_unit": "mg/dL",
        "target_unit": "mmol/L",
        "factor": 1.0 / 18.0182,
        "offset": 0.0,
        "formula": "mmol/L = mg/dL / 18.0182",
        "dimension": "concentration",
        "realm": "pratique",
    },
    {
        "source_unit": "mmol/L",
        "target_unit": "mg/dL",
        "factor": 18.0182,
        "offset": 0.0,
        "formula": "mg/dL = mmol/L * 18.0182",
        "dimension": "concentration",
        "realm": "pratique",
    },
    # Time
    {
        "source_unit": "hours",
        "target_unit": "seconds",
        "factor": 3600.0,
        "offset": 0.0,
        "formula": "seconds = hours * 3600",
        "dimension": "time",
        "realm": "squadron",
    },
    {
        "source_unit": "seconds",
        "target_unit": "hours",
        "factor": 1.0 / 3600.0,
        "offset": 0.0,
        "formula": "hours = seconds / 3600",
        "dimension": "time",
        "realm": "squadron",
    },
]


def convert_unit(value: float, source_unit: str, target_unit: str) -> float:
    """Convert a numeric scalar value from source_unit to target_unit.

    Supports linear scaling and affine transformations (such as Fahrenheit <-> Celsius).
    Raises ValueError if conversion between units is unregistered.
    """
    if source_unit == target_unit:
        return value

    # Temperature special cases
    if source_unit == "degF" and target_unit == "degC":
        return (value - 32.0) * (5.0 / 9.0)
    if source_unit == "degC" and target_unit == "degF":
        return (value * (9.0 / 5.0)) + 32.0
    if source_unit == "degC" and target_unit == "K":
        return value + 273.15
    if source_unit == "K" and target_unit == "degC":
        return value - 273.15
    if source_unit == "degF" and target_unit == "K":
        return ((value - 32.0) * (5.0 / 9.0)) + 273.15

    for rule in UNIT_CONVERSIONS:
        if rule["source_unit"] == source_unit and rule["target_unit"] == target_unit:
            offset = rule.get("offset", 0.0)
            factor = rule["factor"]
            return (value + offset) * factor

    raise ValueError(f"No unit conversion registered for '{source_unit}' -> '{target_unit}'")


# ---------------------------------------------------------------------------
# Schema Generators
# ---------------------------------------------------------------------------

def generate_parquet_table_contract(realm: str) -> Dict[str, Any]:
    """Generate an Apache Parquet table contract object conforming to parquet-contracts.schema.json."""
    normalized_realm = realm.replace("-", "_").lower()
    if normalized_realm in ("pratique", "13_pratique"):
        canonical_realm = "pratique"
        table_name = "pratique_telemetry"
        columns = PRATIQUE_COLUMNS
        conversions = [c for c in UNIT_CONVERSIONS if c.get("realm") in ("pratique", "global")]
    elif normalized_realm in ("squadron", "16_squadron"):
        canonical_realm = "squadron"
        table_name = "squadron_telemetry"
        columns = SQUADRON_COLUMNS
        conversions = [c for c in UNIT_CONVERSIONS if c.get("realm") in ("squadron", "global")]
    elif normalized_realm in ("the_glass", "30_the_glass"):
        canonical_realm = "the_glass"
        table_name = "the_glass_telemetry"
        columns = THE_GLASS_COLUMNS
        conversions = [c for c in UNIT_CONVERSIONS if c.get("realm") in ("the_glass", "global")]
    else:
        raise ValueError(f"Unknown Archetype 3 realm: {realm!r}")

    return {
        "realm": canonical_realm,
        "table_name": table_name,
        "primary_key": "timestamp_utc",
        "columns": columns,
        "unit_conversions": conversions,
        "schema_version": "1.0.0",
        "description": f"Canonical Apache Parquet table layout contract for {canonical_realm}.",
    }


def generate_parquet_schema_definition(realm: str) -> Dict[str, Any]:
    """Generate a Parquet/PyArrow field definition object conforming to parquet-contracts.schema.json."""
    normalized_realm = realm.replace("-", "_").lower()
    if normalized_realm in ("pratique", "13_pratique"):
        canonical_realm = "pratique"
        table_name = "pratique_telemetry"
        columns = PRATIQUE_COLUMNS
    elif normalized_realm in ("squadron", "16_squadron"):
        canonical_realm = "squadron"
        table_name = "squadron_telemetry"
        columns = SQUADRON_COLUMNS
    elif normalized_realm in ("the_glass", "30_the_glass"):
        canonical_realm = "the_glass"
        table_name = "the_glass_telemetry"
        columns = THE_GLASS_COLUMNS
    else:
        raise ValueError(f"Unknown Archetype 3 realm: {realm!r}")

    return {
        "realm": canonical_realm,
        "table_name": table_name,
        "fields": columns,
        "metadata": {
            "archetype": "dual-track-telemetry",
            "spec_version": "1.0.0",
            "time_column": "timestamp_utc",
        },
    }


def generate_telemetry_catalog() -> Dict[str, Any]:
    """Generate the full fleet-wide telemetry catalog object conforming to parquet-contracts.schema.json."""
    return {
        "version": "1.0.0",
        "archetype": "dual-track-telemetry",
        "contracts": {
            "pratique": generate_parquet_table_contract("pratique"),
            "squadron": generate_parquet_table_contract("squadron"),
            "the_glass": generate_parquet_table_contract("the_glass"),
        },
        "unit_conversions": UNIT_CONVERSIONS,
    }


def generate_sample_record(realm: str, **overrides: Any) -> Dict[str, Any]:
    """Generate a canonical row record for testing and ingestion validation."""
    normalized_realm = realm.replace("-", "_").lower()
    if normalized_realm in ("pratique", "13_pratique"):
        base = {
            "timestamp_utc": 1726588800000000,
            "metric_type": "heart_rate",
            "value": 72.0,
            "unit": "bpm",
            "sensor_id": "sensor-polar-h10-01",
        }
    elif normalized_realm in ("squadron", "16_squadron"):
        base = {
            "timestamp_utc": 1726588800000000,
            "vin": "1HGCR2F83HA000000",
            "engine_hours": 142.5,
            "pid_code": "010C",
            "raw_value": 2400.0,
        }
    elif normalized_realm in ("the_glass", "30_the_glass"):
        base = {
            "timestamp_utc": 1726588800000000,
            "station_id": "buoy-station-44013",
            "barometric_hpa": 1013.25,
            "tidal_height_m": 2.45,
        }
    else:
        raise ValueError(f"Unknown Archetype 3 realm: {realm!r}")

    base.update(overrides)
    return base


def generate_sample_batch(realm: str, count: int = 5) -> Dict[str, Any]:
    """Generate a recordBatch envelope with multiple valid observations."""
    canonical_realm = realm.replace("-", "_").lower()
    if canonical_realm.startswith("13_"):
        canonical_realm = "pratique"
    elif canonical_realm.startswith("16_"):
        canonical_realm = "squadron"
    elif canonical_realm.startswith("30_"):
        canonical_realm = "the_glass"

    records = []
    base_ts = 1726588800000000
    for i in range(count):
        ts = base_ts + (i * 1000000)
        if canonical_realm == "pratique":
            rec = generate_sample_record("pratique", timestamp_utc=ts, value=70.0 + (i * 1.5))
        elif canonical_realm == "squadron":
            rec = generate_sample_record("squadron", timestamp_utc=ts, raw_value=2000.0 + (i * 100.0))
        elif canonical_realm == "the_glass":
            rec = generate_sample_record("the_glass", timestamp_utc=ts, barometric_hpa=1013.0 + (i * 0.2))
        else:
            raise ValueError(f"Unknown realm: {realm}")
        records.append(rec)

    return {
        "realm": canonical_realm,
        "records": records,
    }


# ---------------------------------------------------------------------------
# CLI & Verification
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fleet Telemetry Parquet Contracts Utility")
    parser.add_argument("--catalog", action="store_true", help="Print full telemetry catalog JSON")
    parser.add_argument("--verify", action="store_true", help="Verify contracts against schema")
    parser.add_argument("--convert", nargs=3, metavar=("VAL", "FROM", "TO"), help="Convert unit: <val> <from> <to>")
    args = parser.parse_args()

    if args.convert:
        val = float(args.convert[0])
        src = args.convert[1]
        dst = args.convert[2]
        res = convert_unit(val, src, dst)
        print(f"{val} {src} = {res:.6f} {dst}")
        return

    if args.catalog:
        catalog = generate_telemetry_catalog()
        print(json.dumps(catalog, indent=2))
        return

    if args.verify:
        try:
            import jsonschema
            from jsonschema import Draft202012Validator
        except ImportError:
            print("jsonschema not installed, skipping schema validation.", file=sys.stderr)
            return

        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)

        validator = Draft202012Validator(schema)
        catalog = generate_telemetry_catalog()
        validator.validate(catalog)
        print("Catalog validates successfully against parquet-contracts.schema.json!")

        for realm in ("pratique", "squadron", "the_glass"):
            tc = generate_parquet_table_contract(realm)
            validator.validate(tc)
            sd = generate_parquet_schema_definition(realm)
            validator.validate(sd)
            rec = generate_sample_record(realm)
            validator.validate(rec)
            batch = generate_sample_batch(realm)
            validator.validate(batch)
            print(f"Realm {realm}: table contract, schema definition, record, and batch verified.")

        print("All Parquet telemetry contracts verified cleanly.")


if __name__ == "__main__":
    main()
