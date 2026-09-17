"""tests/test_lint_realm_schemas.py
─────────────────────────────────
Test suite verifying the multi-realm schema linting and drift detection script.

Verifies:
  1. Programmatic execution over canonical schemas/v1/realms/ produces 0 violations.
  2. Flags unpinned or mismatched $id URIs.
  3. Flags incorrect archetype inheritance in allOf composition.
  4. Flags property leaks outside the scoped delta block (e.g. root properties).
  5. Flags missing documentation strings (schema title/desc, property desc).
  6. Flags attribute drift (missing canonical delta attributes).
  7. CLI entrypoint exits cleanly with returncode 0.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lint_realm_schemas import (
    REALM_SPECIFICATIONS,
    RealmSchemaLinter,
    run_linter,
)

_LINT_SCRIPT = _REPO_ROOT / "scripts" / "lint_realm_schemas.py"


class TestRealmSchemaLinter(unittest.TestCase):
    """Test suite for RealmSchemaLinter."""

    def test_canonical_realms_have_zero_violations(self):
        """The 50 canonical realm schemas in the repo must have zero linting violations."""
        linter = RealmSchemaLinter()
        violations = linter.lint_all_realms()
        self.assertEqual(
            violations,
            [],
            f"Found unexpected violations: {[f'{v.realm_key}: {v.message}' for v in violations]}",
        )

    def test_cli_execution_exits_zero(self):
        """CLI invocation of scripts/lint_realm_schemas.py must exit with code 0."""
        result = subprocess.run(
            [sys.executable, str(_LINT_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, f"Script failed:\n{result.stdout}\n{result.stderr}")
        self.assertIn("SUCCESS: All 50 realm schemas conform strictly", result.stdout)

    def test_cli_verbose_execution_exits_zero(self):
        """CLI invocation with --verbose flag must display individual realm passes."""
        result = subprocess.run(
            [sys.executable, str(_LINT_SCRIPT), "--verbose"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("[PASS] Realm 01-bosun", result.stdout)
        self.assertIn("[PASS] Realm 50-relay", result.stdout)

    def test_detects_unpinned_id(self):
        """Linter flags unpinned or incorrect $id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_realms = pathlib.Path(tmpdir) / "realms"
            tmp_realms.mkdir()

            # Copy 01-bosun but corrupt $id
            source = _REPO_ROOT / "schemas" / "v1" / "realms" / "01-bosun.schema.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            data["$id"] = "https://unpinned.com/wrong.json"
            (tmp_realms / "01-bosun.schema.json").write_text(json.dumps(data), encoding="utf-8")

            linter = RealmSchemaLinter(realms_dir=tmp_realms)
            linter._lint_realm_schema("01-bosun", tmp_realms / "01-bosun.schema.json", "stage-gate-manifest.schema.json", "bosun", ["zettel_type", "wikilinks", "ast_version"])
            violations = [v for v in linter.violations if v.category == "id-pinning"]
            self.assertTrue(len(violations) >= 1)
            self.assertIn("Unpinned or mismatched $id", violations[0].message)

    def test_detects_archetype_inheritance_mismatch(self):
        """Linter flags when realm does not inherit from its assigned archetype."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_realms = pathlib.Path(tmpdir) / "realms"
            tmp_realms.mkdir()

            source = _REPO_ROOT / "schemas" / "v1" / "realms" / "01-bosun.schema.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            data["allOf"][0]["$ref"] = "https://bosunpkm.com/schemas/v1/archetypes/catalog-dossier.schema.json"
            (tmp_realms / "01-bosun.schema.json").write_text(json.dumps(data), encoding="utf-8")

            linter = RealmSchemaLinter(realms_dir=tmp_realms)
            linter._lint_realm_schema("01-bosun", tmp_realms / "01-bosun.schema.json", "stage-gate-manifest.schema.json", "bosun", ["zettel_type", "wikilinks", "ast_version"])
            violations = [v for v in linter.violations if v.category == "inheritance"]
            self.assertTrue(len(violations) >= 1)
            self.assertIn("Assigned archetype mismatch", violations[0].message)

    def test_detects_property_leakage_outside_delta_block(self):
        """Linter flags root-level properties leaked outside delta block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_realms = pathlib.Path(tmpdir) / "realms"
            tmp_realms.mkdir()

            source = _REPO_ROOT / "schemas" / "v1" / "realms" / "01-bosun.schema.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            data["properties"] = {"leaked_property": {"type": "string"}}
            (tmp_realms / "01-bosun.schema.json").write_text(json.dumps(data), encoding="utf-8")

            linter = RealmSchemaLinter(realms_dir=tmp_realms)
            linter._lint_realm_schema("01-bosun", tmp_realms / "01-bosun.schema.json", "stage-gate-manifest.schema.json", "bosun", ["zettel_type", "wikilinks", "ast_version"])
            violations = [v for v in linter.violations if v.category == "scope-leak"]
            self.assertTrue(len(violations) >= 1)
            self.assertIn("Root-level 'properties' found", violations[0].message)

    def test_detects_missing_documentation_string(self):
        """Linter flags property missing description string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_realms = pathlib.Path(tmpdir) / "realms"
            tmp_realms.mkdir()

            source = _REPO_ROOT / "schemas" / "v1" / "realms" / "01-bosun.schema.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            del data["allOf"][2]["properties"]["wikilinks"]["description"]
            (tmp_realms / "01-bosun.schema.json").write_text(json.dumps(data), encoding="utf-8")

            linter = RealmSchemaLinter(realms_dir=tmp_realms)
            linter._lint_realm_schema("01-bosun", tmp_realms / "01-bosun.schema.json", "stage-gate-manifest.schema.json", "bosun", ["zettel_type", "wikilinks", "ast_version"])
            violations = [v for v in linter.violations if v.category == "documentation"]
            self.assertTrue(len(violations) >= 1)
            self.assertIn("missing a 'description'", violations[0].message)

    def test_detects_delta_attribute_drift(self):
        """Linter flags missing canonical delta attribute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_realms = pathlib.Path(tmpdir) / "realms"
            tmp_realms.mkdir()

            source = _REPO_ROOT / "schemas" / "v1" / "realms" / "01-bosun.schema.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            del data["allOf"][2]["properties"]["wikilinks"]
            (tmp_realms / "01-bosun.schema.json").write_text(json.dumps(data), encoding="utf-8")

            linter = RealmSchemaLinter(realms_dir=tmp_realms)
            linter._lint_realm_schema("01-bosun", tmp_realms / "01-bosun.schema.json", "stage-gate-manifest.schema.json", "bosun", ["zettel_type", "wikilinks", "ast_version"])
            violations = [v for v in linter.violations if v.category == "drift"]
            self.assertTrue(len(violations) >= 1)
            self.assertIn("Missing canonical delta attribute 'wikilinks'", violations[0].message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
