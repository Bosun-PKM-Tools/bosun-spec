"""tests/test_federated_query_fixtures.py
────────────────────────────────────────
Integration suite for federated query-plan fixtures under
``tests/fixtures/queries/federated/``:

  1. Load ``schemas/v1/query/federated-query-plan.schema.json`` as Draft 2020-12.
  2. Valid fixtures MUST pass jsonschema validation:
     - ``primary-archive-join.json`` — two-vault sovereign bridge joining
       live Trice/Yeoman notes in Primary to historical Careen/Commonplace
       notes in Archive on shared entity URNs.
  3. Invalid fixtures MUST raise ``ValidationError``:
     - ``invalid-unknown-vault.json`` — join step ``target_vault`` uses an
       illegal vault alias (``ghost.vault``).
     - ``invalid-missing-join-key.json`` — empty ``join_keys`` object (oneOf).

Usage
  python tests/test_federated_query_fixtures.py
  python -m pytest tests/test_federated_query_fixtures.py -v
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "federated-query-plan.schema.json"
_FIXTURES_DIR = pathlib.Path(__file__).resolve().parent / "fixtures" / "queries" / "federated"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID = "https://bosunpkm.com/schemas/v1/query/federated-query-plan.schema.json"

_TRICE_TASK = "urn:trice:task:018f3a00-0000-7000-8000-000000000003"
_CAREEN_PROJECT = "urn:careen:project:018f3a00-0000-7000-8000-000000000009"

_VALID_FIXTURES = (
    "primary-archive-join.json",
)
_INVALID_FIXTURES = (
    "invalid-unknown-vault.json",
    "invalid-missing-join-key.json",
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
class TestFederatedQueryFixtures(unittest.TestCase):
    """Validate federated query-plan fixtures against Draft 2020-12."""

    @classmethod
    def setUpClass(cls):
        if not _SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Schema not found at {_SCHEMA_PATH}")
        cls.schema_json = _load_json(_SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema_json)
        cls.validator = Draft202012Validator(cls.schema_json)

    def test_schema_declares_draft_and_canonical_id(self):
        """Fixtures validate against the pinned federated query-plan Draft 2020-12 schema."""
        self.assertEqual(self.schema_json.get("$schema"), _DRAFT_2020_12)
        self.assertEqual(self.schema_json.get("$id"), _CANONICAL_ID)

    def test_expected_federated_fixtures_exist(self):
        """Catalogued valid and invalid federated fixtures must be present."""
        self.assertTrue(_FIXTURES_DIR.is_dir(), f"Missing {_FIXTURES_DIR}")
        for name in _VALID_FIXTURES + _INVALID_FIXTURES:
            with self.subTest(fixture=name):
                path = _FIXTURES_DIR / name
                self.assertTrue(path.is_file(), f"Missing fixture: {path}")

    def test_valid_query_fixtures_pass_draft_2020_12(self):
        """Valid federated query plans must pass jsonschema validation."""
        for name in _VALID_FIXTURES:
            with self.subTest(fixture=name):
                payload = _load_json(_FIXTURES_DIR / name)
                try:
                    self.validator.validate(payload)
                except ValidationError as exc:
                    self.fail(
                        f"{name} should be a valid federated query plan: {exc.message}\n"
                        f"Failed path: {list(exc.path)}\n"
                        f"Schema path: {list(exc.schema_path)}"
                    )

    def test_invalid_query_fixtures_fail_draft_2020_12(self):
        """Invalid federated query plans must raise ValidationError."""
        for name in _INVALID_FIXTURES:
            with self.subTest(fixture=name):
                payload = _load_json(_FIXTURES_DIR / name)
                with self.assertRaises(ValidationError):
                    self.validator.validate(payload)

    def test_primary_archive_join_bridges_two_sovereign_vaults(self):
        """Valid fixture joins Primary Trice/Yeoman live notes to Archive Careen/Commonplace."""
        payload = _load_json(_FIXTURES_DIR / "primary-archive-join.json")
        endpoints = payload["vault_endpoints"]
        self.assertEqual(set(endpoints), {"primary", "archive"})
        self.assertEqual(endpoints["primary"]["type"], "local")
        self.assertEqual(endpoints["archive"]["type"], "stdio_rpc")

        steps_by_id = {step["step_id"]: step for step in payload["distributed_steps"]}
        primary_step = steps_by_id["scan_primary_live_notes"]
        archive_step = steps_by_id["scan_archive_historical_notes"]
        join_step = steps_by_id["join_primary_archive_urns"]

        self.assertEqual(primary_step["target_vault"], "primary")
        self.assertEqual(primary_step["query"]["linked_from"], _TRICE_TASK)
        self.assertEqual(set(primary_step["query"]["match_realm"]), {"trice", "yeoman"})
        self.assertEqual(primary_step["query"]["has_relation"], "assignedToContact")

        self.assertEqual(archive_step["target_vault"], "archive")
        self.assertEqual(archive_step["query"]["linked_from"], _CAREEN_PROJECT)
        self.assertEqual(
            set(archive_step["query"]["match_realm"]),
            {"careen", "commonplace"},
        )

        self.assertEqual(join_step["operation"], "join")
        self.assertEqual(join_step["join_key"], "task_derived_from_project")
        self.assertEqual(join_step["input_from_step"], "scan_primary_live_notes")
        self.assertEqual(join_step["join_with_step"], "scan_archive_historical_notes")

        join_key = payload["join_keys"]["task_derived_from_project"]
        self.assertEqual(join_key["matching_strategy"], "exact_urn")
        self.assertEqual(join_key["source_field"], "$pkm.relations.actionItemDerivedFrom")
        self.assertEqual(join_key["target_field"], "$pkm.id")

    def test_invalid_unknown_vault_is_rejected_for_target_vault(self):
        """Unknown vault alias must fail schema validation at target_vault."""
        payload = _load_json(_FIXTURES_DIR / "invalid-unknown-vault.json")
        join_step = payload["distributed_steps"][1]
        self.assertEqual(join_step["target_vault"], "ghost.vault")
        errors = list(self.validator.iter_errors(payload))
        self.assertTrue(errors, "expected ValidationError for unknown vault id")
        paths = [path for err in errors for path in _iter_error_paths(err)]
        self.assertTrue(
            any(path and path[-1] == "target_vault" for path in paths),
            f"expected a target_vault error, got: {[e.message for e in errors]}",
        )

    def test_invalid_missing_join_key_walks_oneof_context(self):
        """Empty join_keys must fail both oneOf branches; walk error.context."""
        payload = _load_json(_FIXTURES_DIR / "invalid-missing-join-key.json")
        self.assertEqual(payload["join_keys"], {})
        errors = list(self.validator.iter_errors(payload))
        self.assertTrue(errors, "expected ValidationError for missing join keys")
        paths = [path for err in errors for path in _iter_error_paths(err)]
        self.assertTrue(
            any(path and path[-1] == "join_keys" for path in paths)
            or any("join_keys" in err.schema_path for err in errors),
            f"expected a join_keys oneOf error, got: {[e.message for e in errors]}",
        )
        oneof_errors = [
            err for err in errors if "oneOf" in list(err.schema_path) or err.context
        ]
        self.assertTrue(
            oneof_errors or any(err.context for err in errors),
            "expected oneOf context on empty join_keys",
        )


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestFederatedQueryFixtures)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
