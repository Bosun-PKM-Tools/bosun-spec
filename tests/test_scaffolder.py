"""tests/test_scaffolder.py
────────────────────────
Test suite verifying the 50-realm vault scaffolding CLI and programmatic workflow.

Verifies:
  1. Scaffolding creates all 50 realm directories (01-bosun through 50-relay).
  2. Each realm directory contains .bosun/state.json initialized manifest with a valid $pkm envelope.
  3. Each realm directory contains an initial starter note based on templates/realms/.
  4. Each starter note's YAML frontmatter contains a valid $pkm envelope (UUIDv7, realm, timestamps).
  5. Each starter note validates cleanly against its respective schemas/v1/realms/<realm>.schema.json
     via Draft 2020-12 validator with archetype and meta-envelope resolution.
  6. The CLI interface (scripts/scaffold_fleet_vault.py) operates cleanly via subprocess.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
import uuid

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.scaffold_fleet_vault import (
    REALM_KEYS,
    generate_uuidv7,
    get_canonical_realm,
    scaffold_fleet_vault,
)
_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_TEMPLATES_DIR = _REPO_ROOT / "templates" / "realms"
_SCAFFOLD_SCRIPT = _REPO_ROOT / "scripts" / "scaffold_fleet_vault.py"

_REQUIRED_ARCHETYPE_SCHEMAS = (
    "v1/archetypes/catalog-dossier.schema.json",
    "v1/archetypes/interaction-ledger.schema.json",
    "v1/archetypes/dual-track-telemetry.schema.json",
    "v1/archetypes/stage-gate-manifest.schema.json",
    "v1/archetypes/sovereign-vault.schema.json",
)

_UUID_URN_PATTERN = re.compile(r"^urn:uuid:([0-9a-fA-F-]{36})$")
_ISO_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?(Z|[+-][0-9]{2}:?[0-9]{2})?)?$"
)


def _extract_frontmatter_and_body(content: str) -> tuple[str, str]:
    """Split a markdown document into raw YAML frontmatter and markdown body."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("Document does not begin with frontmatter delimiter '---'")
    closing_index = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_index = idx
            break
    if closing_index == -1:
        raise ValueError("Document is missing closing frontmatter delimiter '---'")
    return "".join(lines[1:closing_index]), "".join(lines[closing_index + 1:])


class TestVaultScaffolder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _HAS_YAML:
            raise unittest.SkipTest("PyYAML not installed")
        if not _HAS_JSONSCHEMA:
            raise unittest.SkipTest("jsonschema not installed")

        # Build referencing Registry with all 5 base archetypes and universal envelope
        cls.registry = Registry()
        for arch_rel in _REQUIRED_ARCHETYPE_SCHEMAS:
            arch_path = _SCHEMAS_DIR / arch_rel
            if not arch_path.exists():
                raise RuntimeError(f"Archetype schema missing: {arch_path}")
            arch_obj = json.loads(arch_path.read_text(encoding="utf-8"))
            cls.registry = cls.registry.with_resource(
                arch_obj["$id"], Resource.from_contents(arch_obj)
            )

        envelope_path = _SCHEMAS_DIR / "v1" / "meta" / "envelope.schema.json"
        if not envelope_path.exists():
            raise RuntimeError(f"Envelope schema missing: {envelope_path}")
        cls.envelope_obj = json.loads(envelope_path.read_text(encoding="utf-8"))
        cls.registry = cls.registry.with_resource(
            cls.envelope_obj["$id"], Resource.from_contents(cls.envelope_obj)
        )

    def test_uuidv7_generator_compliance(self):
        """Generated UUID strings must be RFC 9562 UUIDv7 with correct version and variant."""
        for _ in range(50):
            val = generate_uuidv7()
            parsed = uuid.UUID(val)
            self.assertEqual(parsed.version, 7, f"Expected UUID version 7, got {parsed.version}")
            self.assertEqual(parsed.variant, uuid.RFC_4122, f"Expected RFC 4122 variant, got {parsed.variant}")

    def test_scaffold_creates_all_50_realm_directories(self):
        """Scaffolding a vault must produce exactly 50 realm directories matching REALM_KEYS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_dir = pathlib.Path(tmpdir) / "test_vault"
            created = scaffold_fleet_vault(vault_dir, templates_dir=_TEMPLATES_DIR)

            self.assertEqual(len(created), 50, f"Expected 50 realms created, got {len(created)}")
            for key in REALM_KEYS:
                with self.subTest(realm=key):
                    expected_path = vault_dir / key
                    self.assertTrue(expected_path.is_dir(), f"Missing realm directory: {expected_path}")
                    self.assertIn(key, created)

    def test_each_realm_has_initialized_state_manifest(self):
        """Each realm directory must contain .bosun/state.json adhering to envelope contract."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_dir = pathlib.Path(tmpdir) / "test_vault"
            scaffold_fleet_vault(vault_dir, templates_dir=_TEMPLATES_DIR)

            envelope_validator = Draft202012Validator(self.envelope_obj, registry=self.registry)

            for key in REALM_KEYS:
                with self.subTest(realm=key):
                    canonical = get_canonical_realm(key)
                    state_file = vault_dir / key / ".bosun" / "state.json"
                    self.assertTrue(state_file.is_file(), f"Missing state file: {state_file}")

                    data = json.loads(state_file.read_text(encoding="utf-8"))
                    self.assertEqual(data["realm"], canonical)
                    self.assertEqual(data["realm_key"], key)
                    self.assertEqual(data["status"], "initialized")
                    self.assertEqual(data["starter_note"], "starter.md")

                    # Validate $pkm envelope
                    self.assertIn("$pkm", data)
                    pkm = data["$pkm"]
                    self.assertEqual(pkm["realm"], canonical)
                    match = _UUID_URN_PATTERN.match(pkm["id"])
                    self.assertIsNotNone(match, f"Invalid UUID URN: {pkm['id']}")
                    self.assertEqual(uuid.UUID(match.group(1)).version, 7)
                    self.assertTrue(_ISO_TIMESTAMP_PATTERN.match(pkm["created_at"]))
                    self.assertTrue(_ISO_TIMESTAMP_PATTERN.match(pkm["updated_at"]))

                    # Validate against meta-envelope schema
                    envelope_validator.validate(data)

    def test_each_realm_produces_valid_realm_envelope_and_schema_conformance(self):
        """Each realm starter note must contain a valid $pkm envelope conforming to its realm schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_dir = pathlib.Path(tmpdir) / "test_vault"
            scaffold_fleet_vault(vault_dir, templates_dir=_TEMPLATES_DIR)

            for key in REALM_KEYS:
                with self.subTest(realm=key):
                    canonical = get_canonical_realm(key)
                    starter_note = vault_dir / key / "starter.md"
                    self.assertTrue(starter_note.is_file(), f"Missing starter note: {starter_note}")

                    raw_content = starter_note.read_text(encoding="utf-8")
                    frontmatter_text, body_text = _extract_frontmatter_and_body(raw_content)

                    # Verify body has title heading and starter sections
                    self.assertTrue(body_text.strip().startswith("# "), f"{key}: body must start with '# '")
                    h2_headings = [l for l in body_text.splitlines() if l.startswith("## ")]
                    self.assertGreaterEqual(len(h2_headings), 2, f"{key}: expected at least 2 section headings")

                    # Parse frontmatter
                    fm = yaml.safe_load(frontmatter_text)
                    self.assertIsInstance(fm, dict, f"{key}: frontmatter must parse as dict")

                    # Verify $pkm universal envelope
                    self.assertIn("$pkm", fm, f"{key}: missing $pkm envelope in starter note")
                    pkm = fm["$pkm"]
                    self.assertEqual(pkm["realm"], canonical)
                    match = _UUID_URN_PATTERN.match(pkm["id"])
                    self.assertIsNotNone(match, f"{key}: invalid UUID URN: {pkm.get('id')}")
                    self.assertEqual(uuid.UUID(match.group(1)).version, 7)
                    self.assertTrue(_ISO_TIMESTAMP_PATTERN.match(str(pkm["created_at"])))
                    self.assertTrue(_ISO_TIMESTAMP_PATTERN.match(str(pkm["updated_at"])))

                    # Validate against realm delta schema
                    schema_file = _SCHEMAS_DIR / "v1" / "realms" / f"{key}.schema.json"
                    self.assertTrue(schema_file.exists(), f"Missing schema for {key}: {schema_file}")
                    schema_obj = json.loads(schema_file.read_text(encoding="utf-8"))

                    validator = Draft202012Validator(schema_obj, registry=self.registry)
                    try:
                        validator.validate(fm)
                    except jsonschema.ValidationError as exc:
                        self.fail(f"Realm {key} starter note failed schema validation: {exc.message}")

    def test_cli_invocation_scaffolds_temp_vault(self):
        """Invoking scripts/scaffold_fleet_vault.py via CLI must successfully initialize a vault."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_dir = pathlib.Path(tmpdir) / "cli_vault"
            cmd = [
                sys.executable,
                str(_SCAFFOLD_SCRIPT),
                str(vault_dir),
                "--starter-filename",
                "starter.md",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(
                result.returncode, 0,
                f"CLI execution failed with returncode {result.returncode}:\n{result.stderr}"
            )
            self.assertIn("Successfully scaffolded 50 realms", result.stdout)

            # Check that realms exist
            for key in REALM_KEYS:
                self.assertTrue((vault_dir / key / ".bosun" / "state.json").exists())
                self.assertTrue((vault_dir / key / "starter.md").exists())


if __name__ == "__main__":
    unittest.main()
