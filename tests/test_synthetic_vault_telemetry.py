"""tests/test_synthetic_vault_telemetry.py
───────────────────────────────────────
Validates that every Parquet partition referenced by synthetic vault notes
exists and matches schemas/v1/telemetry/parquet-contracts.schema.json.

Checks:
  1. Notes that declare telemetry_parquet_ref (or telemetry.parquet_ref)
     point at files that exist under fixtures/synthetic_vault/.
  2. At least one Parquet partition is referenced (the Dual-Track Telemetry
     invariant for this vault).
  3. Footer schema metadata (field names, physical/logical types, nullability)
     matches the realm record contract in parquet-contracts.schema.json.
  4. Extracted schema objects themselves validate as parquetSchemaDefinition
     under JSON Schema Draft 2020-12.
  5. Missing files, extra/missing fields, type mismatches, and nullability
     mismatches fail with explicit messages.

Usage:
  python tests/test_synthetic_vault_telemetry.py
  python -m pytest tests/test_synthetic_vault_telemetry.py -v
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from typing import Any, Dict, List

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.generate_synthetic_vault import collect_telemetry_parquet_refs
from scripts.parquet_codec import (
    canonicalize_contract_type,
    canonicalize_logical_type,
    fields_from_record_contract,
    read_parquet_schema,
    write_parquet_table,
)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_VAULT_DIR = _REPO_ROOT / "fixtures" / "synthetic_vault"
_CONTRACT_PATH = _SCHEMAS_DIR / "v1" / "telemetry" / "parquet-contracts.schema.json"
_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"

_TABLE_NAME_BY_REALM = {
    "pratique": "pratique_telemetry",
    "13-pratique": "pratique_telemetry",
    "squadron": "squadron_telemetry",
    "16-squadron": "squadron_telemetry",
    "the-glass": "the_glass_telemetry",
    "the_glass": "the_glass_telemetry",
    "30-the-glass": "the_glass_telemetry",
}

_CANONICAL_REALM = {
    "pratique": "pratique",
    "13-pratique": "pratique",
    "squadron": "squadron",
    "16-squadron": "squadron",
    "the-glass": "the_glass",
    "the_glass": "the_glass",
    "30-the-glass": "the_glass",
}


def expected_fields_for_realm(contract: Dict[str, Any], realm: str) -> List[Dict[str, Any]]:
    """Derive expected Parquet columns from the realm record $def (source of truth)."""
    try:
        return fields_from_record_contract(contract, realm)
    except ValueError as exc:
        raise AssertionError(str(exc)) from exc


def _field_index(fields: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {field["name"]: field for field in fields}


def _compare_schema(
    parquet_path: pathlib.Path,
    actual: List[Dict[str, Any]],
    expected: List[Dict[str, Any]],
) -> List[str]:
    """Return human-readable mismatch messages for names, types, and nullability."""
    errors: List[str] = []
    actual_names = [field["name"] for field in actual]
    expected_names = [field["name"] for field in expected]
    missing = [name for name in expected_names if name not in actual_names]
    extra = [name for name in actual_names if name not in expected_names]
    if missing:
        errors.append(
            f"{parquet_path}: missing fields {missing}; expected {expected_names}, found {actual_names}"
        )
    if extra:
        errors.append(
            f"{parquet_path}: extra fields {extra}; expected {expected_names}, found {actual_names}"
        )

    actual_map = _field_index(actual)
    expected_map = _field_index(expected)
    for name, exp in expected_map.items():
        got = actual_map.get(name)
        if got is None:
            continue
        exp_type = canonicalize_contract_type(exp["type"])
        got_type = canonicalize_contract_type(got["type"])
        if exp_type != got_type:
            errors.append(
                f"{parquet_path}: type mismatch for {name!r}: expected {exp_type}, found {got_type}"
            )
        exp_logical = canonicalize_logical_type(exp.get("logical_type"))
        got_logical = canonicalize_logical_type(got.get("logical_type"))
        if exp_logical != got_logical:
            errors.append(
                f"{parquet_path}: logical type mismatch for {name!r}: "
                f"expected {exp_logical}, found {got_logical}"
            )
        if bool(exp.get("nullable", False)) != bool(got.get("nullable", False)):
            errors.append(
                f"{parquet_path}: nullability mismatch for {name!r}: "
                f"expected nullable={bool(exp.get('nullable', False))}, "
                f"found nullable={bool(got.get('nullable', False))}"
            )
    return errors


def _schema_definition_object(
    realm: str, parquet_path: pathlib.Path, fields: List[Dict[str, Any]]
) -> Dict[str, Any]:
    canonical = _CANONICAL_REALM[realm]
    return {
        "realm": canonical,
        "table_name": _TABLE_NAME_BY_REALM[realm],
        "fields": [
            {
                "name": field["name"],
                "type": field["type"],
                "logical_type": field["logical_type"],
                "nullable": bool(field.get("nullable", False)),
            }
            for field in fields
        ],
        "metadata": {
            "source": str(parquet_path.relative_to(_VAULT_DIR)).replace("\\", "/"),
            "archetype": "dual-track-telemetry",
        },
    }


class TestSyntheticVaultTelemetry(unittest.TestCase):
    """Parquet partitions referenced by the synthetic vault must match the contract."""

    @classmethod
    def setUpClass(cls) -> None:
        if not _CONTRACT_PATH.is_file():
            raise FileNotFoundError(
                f"Parquet contract missing: {_CONTRACT_PATH}. "
                "Expected schemas/v1/telemetry/parquet-contracts.schema.json on this branch."
            )
        with open(_CONTRACT_PATH, encoding="utf-8") as fh:
            cls.contract = json.load(fh)
        if _HAS_JSONSCHEMA:
            Draft202012Validator.check_schema(cls.contract)
            cls.validator = Draft202012Validator(cls.contract)
        cls.jobs = collect_telemetry_parquet_refs(_VAULT_DIR)

    def test_contract_declares_draft_2020_12(self) -> None:
        """parquet-contracts.schema.json must pin JSON Schema Draft 2020-12."""
        self.assertEqual(self.contract.get("$schema"), _DRAFT_2020_12)

    def test_notes_reference_at_least_one_parquet_partition(self) -> None:
        """The Dual-Track Telemetry invariant requires note-referenced sample partitions."""
        self.assertTrue(
            self.jobs,
            "Synthetic vault notes reference zero Parquet files; Dual-Track Telemetry "
            "realms (pratique, squadron, the-glass) must declare telemetry_parquet_ref "
            "and corresponding sample partitions under fixtures/synthetic_vault/.",
        )

    def test_referenced_parquet_files_exist(self) -> None:
        """Every telemetry_parquet_ref must resolve to a file under the vault."""
        self.assertTrue(self.jobs, "No telemetry_parquet_ref values discovered in synthetic vault notes")
        missing = []
        for rel_path, job in self.jobs.items():
            dest = _VAULT_DIR / pathlib.PurePosixPath(rel_path)
            if not dest.is_file():
                missing.append(f"{rel_path} (from {job['note']})")
        self.assertFalse(
            missing,
            "Referenced Parquet partitions are missing:\n  " + "\n  ".join(missing),
        )

    def test_referenced_parquet_schemas_match_contract(self) -> None:
        """Footer field names, types, and nullability must match the realm record contract."""
        self.assertTrue(self.jobs, "No telemetry_parquet_ref values discovered in synthetic vault notes")
        mismatches: List[str] = []
        for rel_path, job in sorted(self.jobs.items()):
            dest = _VAULT_DIR / pathlib.PurePosixPath(rel_path)
            with self.subTest(parquet=rel_path, note=job["note"]):
                self.assertTrue(dest.is_file(), f"Missing Parquet file {dest} referenced by {job['note']}")
                actual = read_parquet_schema(dest)
                expected = expected_fields_for_realm(self.contract, job["realm"])
                mismatches.extend(_compare_schema(dest, actual, expected))
        self.assertFalse(mismatches, "Parquet schema mismatches:\n  " + "\n  ".join(mismatches))

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_extracted_schema_validates_as_parquet_schema_definition(self) -> None:
        """Arrow/Parquet metadata projected into parquetSchemaDefinition must satisfy the contract."""
        self.assertTrue(self.jobs, "No telemetry_parquet_ref values discovered in synthetic vault notes")
        for rel_path, job in sorted(self.jobs.items()):
            dest = _VAULT_DIR / pathlib.PurePosixPath(rel_path)
            with self.subTest(parquet=rel_path):
                actual = read_parquet_schema(dest)
                payload = _schema_definition_object(job["realm"], dest, actual)
                errors = sorted(self.validator.iter_errors(payload), key=lambda err: list(err.path))
                self.assertFalse(
                    errors,
                    f"{rel_path} schema definition is invalid:\n"
                    + "\n".join(f"  {list(err.path)}: {err.message}" for err in errors),
                )

    def test_codec_roundtrip_preserves_schema_metadata(self) -> None:
        """Stdlib codec must round-trip field names, types, and nullability."""
        columns = expected_fields_for_realm(self.contract, "pratique")
        rows = [
            {
                "timestamp_utc": 1726588800000000,
                "metric_type": "heart_rate",
                "value": 72.0,
                "unit": "bpm",
                "sensor_id": "roundtrip-sensor",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "roundtrip.parquet"
            write_parquet_table(path, columns, rows)
            actual = read_parquet_schema(path)
        self.assertEqual([f["name"] for f in actual], [f["name"] for f in columns])
        errors = _compare_schema(path, actual, columns)
        self.assertFalse(errors, errors)

    def test_mismatch_helpers_fail_clearly(self) -> None:
        """Extra fields, missing fields, type errors, and nullability errors are explicit."""
        expected = expected_fields_for_realm(self.contract, "squadron")
        extra = expected + [
            {"name": "bonus_col", "type": "DOUBLE", "logical_type": "NONE", "nullable": False}
        ]
        extra_errors = _compare_schema(pathlib.Path("x.parquet"), extra, expected)
        self.assertTrue(any("extra fields" in msg for msg in extra_errors), extra_errors)

        missing = expected[:-1]
        missing_errors = _compare_schema(pathlib.Path("x.parquet"), missing, expected)
        self.assertTrue(any("missing fields" in msg for msg in missing_errors), missing_errors)

        wrong_type = [dict(field) for field in expected]
        wrong_type[0]["type"] = "DOUBLE"
        type_errors = _compare_schema(pathlib.Path("x.parquet"), wrong_type, expected)
        self.assertTrue(any("type mismatch" in msg for msg in type_errors), type_errors)

        wrong_null = [dict(field) for field in expected]
        wrong_null[1]["nullable"] = True
        null_errors = _compare_schema(pathlib.Path("x.parquet"), wrong_null, expected)
        self.assertTrue(any("nullability mismatch" in msg for msg in null_errors), null_errors)


if __name__ == "__main__":
    unittest.main()
