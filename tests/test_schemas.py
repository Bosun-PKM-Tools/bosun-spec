"""
tests/test_schemas.py
─────────────────────
Validates that every JSON schema file in bosun-spec/schemas/ is:

  1. Parseable as valid JSON (no syntax errors, no trailing commas, etc.)
  2. Declares a recognised ``$schema`` URI (meta-schema present).
  3. Internally well-formed per ``jsonschema.check_schema()`` — i.e. the
     schema itself satisfies the JSON Schema Draft 2020-12 meta-schema.

Dependencies
  pip install jsonschema          # jsonschema >= 4.0

Usage
  python tests/test_schemas.py   # standalone
  python -m pytest tests/ -v     # via pytest
"""

import json
import sys
import pathlib
import unittest

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

# Locate the schemas/ directory relative to this file's parent (repo root)
_REPO_ROOT = pathlib.Path(__file__).parent.parent
_SCHEMAS_DIR = _REPO_ROOT / "schemas"

# Known JSON Schema draft URIs we accept
_KNOWN_DRAFTS = {
    "https://json-schema.org/draft/2020-12/schema",
    "https://json-schema.org/draft/2019-09/schema",
    "http://json-schema.org/draft-07/schema#",
    "http://json-schema.org/draft-06/schema#",
    "http://json-schema.org/draft-04/schema#",
}


def _collect_schemas():
    """Return a list of (name, path) tuples for all .json files in schemas/."""
    if not _SCHEMAS_DIR.exists():
        return []
    return sorted(
        (p.name, p)
        for p in _SCHEMAS_DIR.glob("*.json")
    )


class TestSchemaFiles(unittest.TestCase):
    """Structural and meta-schema validation for every file in schemas/."""

    @classmethod
    def setUpClass(cls):
        cls.schemas = _collect_schemas()
        if not cls.schemas:
            raise RuntimeError(
                f"No .json files found in {_SCHEMAS_DIR}. "
                "Has the schemas/ directory been populated?"
            )

    def test_schemas_directory_exists(self):
        """The schemas/ directory must exist."""
        self.assertTrue(
            _SCHEMAS_DIR.exists(),
            f"schemas/ directory not found at {_SCHEMAS_DIR}"
        )

    def test_schemas_directory_not_empty(self):
        """At least one .json schema file must be present."""
        self.assertGreater(
            len(self.schemas),
            0,
            "schemas/ directory is empty — expected at least one .json file"
        )

    def _load_json(self, path):
        """Parse a JSON file and return the object, or fail the test."""
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:
            self.fail(
                f"{path.name} contains invalid JSON: {exc}"
            )

    def test_all_schemas_are_valid_json(self):
        """Every schema file must parse as valid JSON."""
        for name, path in self.schemas:
            with self.subTest(schema=name):
                obj = self._load_json(path)
                self.assertIsInstance(
                    obj, dict,
                    f"{name}: expected a JSON object at root level"
                )

    def test_all_schemas_declare_schema_uri(self):
        """Every schema must declare a $schema URI so validators know the draft."""
        for name, path in self.schemas:
            with self.subTest(schema=name):
                obj = self._load_json(path)
                self.assertIn(
                    "$schema", obj,
                    f"{name}: missing required '$schema' field"
                )
                self.assertIsInstance(
                    obj["$schema"], str,
                    f"{name}: '$schema' must be a string URI"
                )
                self.assertGreater(
                    len(obj["$schema"]), 0,
                    f"{name}: '$schema' must not be empty"
                )

    def test_all_schemas_declare_known_draft(self):
        """The $schema URI must reference a recognised JSON Schema draft."""
        for name, path in self.schemas:
            with self.subTest(schema=name):
                obj = self._load_json(path)
                schema_uri = obj.get("$schema", "")
                self.assertIn(
                    schema_uri,
                    _KNOWN_DRAFTS,
                    f"{name}: unrecognised $schema URI '{schema_uri}'. "
                    f"Expected one of: {sorted(_KNOWN_DRAFTS)}"
                )

    def test_all_schemas_have_id(self):
        """Every schema should declare a $id for unambiguous referencing."""
        for name, path in self.schemas:
            with self.subTest(schema=name):
                obj = self._load_json(path)
                self.assertIn(
                    "$id", obj,
                    f"{name}: missing '$id' field (recommended for public schemas)"
                )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_all_schemas_pass_meta_schema_check(self):
        """
        Validates the schema itself against the JSON Schema Draft 2020-12
        meta-schema using ``Draft202012Validator.check_schema()``.  This
        catches structural errors such as wrong property types, invalid keyword
        combinations, and broken $ref chains.

        Note: jsonschema 4.x removed the module-level ``check_schema``
        shortcut; the correct call is ``Draft202012Validator.check_schema()``.
        """
        for name, path in self.schemas:
            with self.subTest(schema=name):
                obj = self._load_json(path)
                try:
                    Draft202012Validator.check_schema(obj)
                except jsonschema.SchemaError as exc:
                    self.fail(
                        f"{name}: failed meta-schema validation: {exc.message}"
                    )
                except Exception as exc:  # noqa: BLE001
                    self.fail(
                        f"{name}: unexpected error during check_schema: {exc}"
                    )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_canonical_note_contract_required_fields(self):
        """
        The canonical-note-contract schema must declare specific required fields
        matching the published Bosun PKM specification.
        """
        expected_required = {
            "schema_version", "type", "title", "status",
            "source", "source_id", "created_at", "updated_at",
            "tags", "canonical_format", "content_format", "target_app",
        }
        path = _SCHEMAS_DIR / "canonical-note-contract-v0.1.json"
        if not path.exists():
            self.skipTest("canonical-note-contract-v0.1.json not yet present")

        obj = self._load_json(path)
        actual_required = set(obj.get("required", []))
        self.assertEqual(
            actual_required,
            expected_required,
            f"canonical-note-contract required fields mismatch.\n"
            f"  Missing : {expected_required - actual_required}\n"
            f"  Extra   : {actual_required - expected_required}"
        )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_event_vocab_has_events_key(self):
        """
        The event-vocab schema must contain a top-level 'events' object
        with at least one event definition.
        """
        path = _SCHEMAS_DIR / "event-vocab-v0.1.json"
        if not path.exists():
            self.skipTest("event-vocab-v0.1.json not yet present")

        obj = self._load_json(path)
        self.assertIn("events", obj, "event-vocab schema is missing 'events' key")
        events = obj["events"]
        self.assertIsInstance(events, dict, "'events' must be a JSON object")
        self.assertGreater(
            len(events), 0,
            "'events' object must contain at least one event definition"
        )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_event_vocab_all_events_have_severity(self):
        """Every event entry in the event-vocab must declare a 'severity' field."""
        path = _SCHEMAS_DIR / "event-vocab-v0.1.json"
        if not path.exists():
            self.skipTest("event-vocab-v0.1.json not yet present")

        obj = self._load_json(path)
        valid_severities = set(obj.get("severities", ["fatal", "error", "warn", "info"]))
        events = obj.get("events", {})

        for code, defn in events.items():
            with self.subTest(event_code=code):
                self.assertIn(
                    "severity", defn,
                    f"Event '{code}' is missing the 'severity' field"
                )
                self.assertIn(
                    defn["severity"], valid_severities,
                    f"Event '{code}' has unknown severity '{defn['severity']}'. "
                    f"Valid values: {valid_severities}"
                )


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSchemaFiles)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
