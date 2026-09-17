"""tests/test_graph_dsl_fixtures.py
──────────────────────────────────
Integration suite for Graph Query DSL fixtures under
``tests/fixtures/queries/``:

  1. Load ``schemas/v1/query/graph-dsl.schema.json`` as Draft 2020-12.
  2. Valid fixtures MUST pass jsonschema validation:
     - ``valid-single-hop-contact.json`` — assignedToContact /
       waitingOnContact / consultedProvider toward a Yeoman contact URN.
     - ``valid-multihop-stage-gate.json`` — Careen/Trice blocked_by /
       depends_on / actionItemDerivedFrom hops.
  3. Invalid fixtures MUST raise ``ValidationError``:
     - ``invalid-negative-depth.json`` — ``max_depth`` below 0.
     - ``invalid-illegal-predicate.json`` — unknown verb (appraisedBy) or
       wrong-realm URN versus ``relations.schema.json``.

Usage
  python tests/test_graph_dsl_fixtures.py
  python -m pytest tests/test_graph_dsl_fixtures.py -v
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "graph-dsl.schema.json"
_FIXTURES_DIR = pathlib.Path(__file__).resolve().parent / "fixtures" / "queries"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID = "https://bosunpkm.com/schemas/v1/query/graph-dsl.schema.json"

_VALID_FIXTURES = (
    "valid-single-hop-contact.json",
    "valid-multihop-stage-gate.json",
)
_INVALID_FIXTURES = (
    "invalid-negative-depth.json",
    "invalid-illegal-predicate.json",
)


def _load_json(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _iter_error_paths(error: ValidationError):
    """Yield JSON Pointer paths from a ValidationError and its oneOf context."""
    yield list(error.path)
    for child in error.context:
        yield from _iter_error_paths(child)


@unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
class TestGraphDslFixtures(unittest.TestCase):
    """Validate Graph DSL query fixtures against Draft 2020-12."""

    @classmethod
    def setUpClass(cls):
        if not _SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Schema not found at {_SCHEMA_PATH}")
        cls.schema_json = _load_json(_SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema_json)
        cls.validator = Draft202012Validator(cls.schema_json)

    def test_schema_declares_draft_and_canonical_id(self):
        """Fixtures validate against the pinned Graph DSL Draft 2020-12 schema."""
        self.assertEqual(self.schema_json.get("$schema"), _DRAFT_2020_12)
        self.assertEqual(self.schema_json.get("$id"), _CANONICAL_ID)

    def test_expected_query_fixtures_exist(self):
        """Catalogued valid and invalid query fixtures must be present."""
        self.assertTrue(_FIXTURES_DIR.is_dir(), f"Missing {_FIXTURES_DIR}")
        for name in _VALID_FIXTURES + _INVALID_FIXTURES:
            with self.subTest(fixture=name):
                path = _FIXTURES_DIR / name
                self.assertTrue(path.is_file(), f"Missing fixture: {path}")

    def test_valid_query_fixtures_pass_draft_2020_12(self):
        """Valid Graph DSL queries must pass jsonschema validation."""
        for name in _VALID_FIXTURES:
            with self.subTest(fixture=name):
                payload = _load_json(_FIXTURES_DIR / name)
                try:
                    self.validator.validate(payload)
                except ValidationError as exc:
                    self.fail(
                        f"{name} should be valid Graph DSL: {exc.message}\n"
                        f"Failed path: {list(exc.path)}\n"
                        f"Schema path: {list(exc.schema_path)}"
                    )

    def test_invalid_query_fixtures_fail_draft_2020_12(self):
        """Invalid Graph DSL queries must raise ValidationError."""
        for name in _INVALID_FIXTURES:
            with self.subTest(fixture=name):
                payload = _load_json(_FIXTURES_DIR / name)
                with self.assertRaises(ValidationError):
                    self.validator.validate(payload)

    def test_valid_single_hop_contact_targets_yeoman_urn(self):
        """Single-hop contact fixture hops toward a Yeoman contact URN."""
        payload = _load_json(_FIXTURES_DIR / "valid-single-hop-contact.json")
        relation = payload["has_relation"]
        self.assertEqual(relation["predicate"], "assignedToContact")
        self.assertTrue(
            str(relation["target"]).startswith("urn:yeoman:contact:"),
            f"expected Yeoman contact URN, got {relation['target']!r}",
        )
        self.assertEqual(payload["max_depth"], 1)
        self.assertIn("waitingOnContact", payload["filters"]["has_relation"])
        self.assertIn("consultedProvider", payload["filters"]["has_relation"])

    def test_valid_multihop_stage_gate_uses_careen_trice_hops(self):
        """Multi-hop stage-gate fixture uses Careen/Trice blocker predicates."""
        payload = _load_json(_FIXTURES_DIR / "valid-multihop-stage-gate.json")
        self.assertGreaterEqual(payload["max_depth"], 2)
        for verb in ("blocked_by", "depends_on", "actionItemDerivedFrom"):
            self.assertIn(verb, payload["has_relation"])
        self.assertIn("stage_gates", payload["edge_types"])
        self.assertEqual(
            set(payload["match_realm"]),
            {"careen", "trice"},
        )

    def test_invalid_negative_depth_is_rejected_for_max_depth(self):
        """Negative max_depth must fail schema validation at that keyword."""
        payload = _load_json(_FIXTURES_DIR / "invalid-negative-depth.json")
        self.assertLess(payload["max_depth"], 0)
        errors = list(self.validator.iter_errors(payload))
        self.assertTrue(errors, "expected ValidationError for negative max_depth")
        paths = [path for err in errors for path in _iter_error_paths(err)]
        self.assertTrue(
            any(path and path[-1] == "max_depth" for path in paths),
            f"expected a max_depth error, got: {[e.message for e in errors]}",
        )

    def test_invalid_illegal_predicate_is_unknown_or_wrong_realm(self):
        """Unknown verb or wrong-realm URN must fail versus relations contract."""
        payload = _load_json(_FIXTURES_DIR / "invalid-illegal-predicate.json")
        relation = payload["has_relation"]
        self.assertEqual(relation["predicate"], "appraisedBy")
        self.assertTrue(
            str(relation["target"]).startswith("urn:qtm:tx:"),
            "fixture should use a QTM txn URN against a non-QTM verb",
        )
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestGraphDslFixtures)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
