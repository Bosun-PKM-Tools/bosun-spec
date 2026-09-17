"""
tests/test_all_fixtures.py
──────────────────────────
Validates all 50 canonical realm markdown fixtures under fixtures/realms/
(01-bosun through 50-relay) against their respective JSON schemas:

  1. Verifies that all 50 realm fixture directories exist and each contains
     a sample markdown file.
  2. Parses the YAML frontmatter and extracts the $pkm envelope.
  3. Verifies that $pkm declares a valid UUIDv7 URN, the exact realm name,
     valid ISO timestamps, and typed URN relations.
  4. Validates the frontmatter against schemas/v1/realms/<realm>.schema.json
     using Draft 2020-12 and resolving base archetypes and the universal
     envelope via the referencing Registry.
  5. Verifies the markdown body contains realistic notes, headings, and
     transclusions matching the domain scope.

Dependencies
  pip install ".[dev]"   # jsonschema, pytest, pyyaml

Usage
  python tests/test_all_fixtures.py
  python -m pytest tests/test_all_fixtures.py -v
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
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
_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_FIXTURES_DIR = _REPO_ROOT / "fixtures" / "realms"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID_PREFIX = "https://bosunpkm.com/schemas/"

_REQUIRED_ARCHETYPE_SCHEMAS = (
    "v1/archetypes/catalog-dossier.schema.json",
    "v1/archetypes/interaction-ledger.schema.json",
    "v1/archetypes/dual-track-telemetry.schema.json",
    "v1/archetypes/stage-gate-manifest.schema.json",
    "v1/archetypes/sovereign-vault.schema.json",
)

_REQUIRED_REALMS = (
    "01-bosun",
    "02-yeoman",
    "03-trice",
    "04-logbook",
    "05-quartermaster",
    "06-harbor",
    "07-press",
    "08-embers",
    "09-careen",
    "10-primer",
    "11-passage",
    "12-galley",
    "13-pratique",
    "14-tactician",
    "15-drydock",
    "16-squadron",
    "17-supercargo",
    "18-commonplace",
    "19-chantey",
    "20-marquee",
    "21-scrimshaw",
    "22-traverse",
    "23-docent",
    "24-proctor",
    "25-ropewalk",
    "26-gavel",
    "27-lineage",
    "28-legacy",
    "29-arbor",
    "30-the-glass",
    "31-dispatch",
    "32-registry",
    "33-purser",
    "34-cadence",
    "35-reckoning",
    "36-strongbox",
    "37-trajectory",
    "38-binnacle",
    "39-claim",
    "40-tribute",
    "41-weft",
    "42-reverie",
    "43-provenance",
    "44-menagerie",
    "45-muster",
    "46-breadboard",
    "47-pavilion",
    "48-charthouse",
    "49-commonwealth",
    "50-relay",
)

_UUID_URN_PATTERN = re.compile(r"^urn:uuid:([0-9a-fA-F-]{36})$")
_ISO_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?(Z|[+-][0-9]{2}:?[0-9]{2})?)?$"
)
_VALID_URN_PATTERN = re.compile(r"^urn:[a-zA-Z0-9_.:-]+$")
_TRANSCLUSION_PATTERN = re.compile(r"!\[\[(.*?)\]\]")
_HEADING_PATTERN = re.compile(r"^#+\s+.+", re.MULTILINE)


def _extract_frontmatter_and_body(content: str) -> tuple[str, str]:
    """Split a markdown string into raw YAML frontmatter and body text."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("File does not begin with frontmatter marker '---'")
    closing_index = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_index = idx
            break
    if closing_index == -1:
        raise ValueError("File is missing closing frontmatter marker '---'")
    frontmatter_text = "".join(lines[1:closing_index])
    body_text = "".join(lines[closing_index + 1:])
    return frontmatter_text, body_text


def _load_json(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestAllRealmFixtures(unittest.TestCase):
    """Validation test suite for all 50 canonical realm test fixtures."""

    @classmethod
    def setUpClass(cls):
        if not _HAS_YAML:
            raise unittest.SkipTest("PyYAML not installed")
        if not _HAS_JSONSCHEMA:
            raise unittest.SkipTest("jsonschema not installed")

        # Build registry with archetype base schemas and universal envelope
        cls.registry = Registry()
        for arch_rel in _REQUIRED_ARCHETYPE_SCHEMAS:
            arch_path = _SCHEMAS_DIR / arch_rel
            if not arch_path.exists():
                raise RuntimeError(f"Missing required archetype schema: {arch_path}")
            arch_obj = _load_json(arch_path)
            cls.registry = cls.registry.with_resource(
                arch_obj["$id"], Resource.from_contents(arch_obj)
            )

        envelope_path = _SCHEMAS_DIR / "v1" / "meta" / "envelope.schema.json"
        if not envelope_path.exists():
            raise RuntimeError(f"Missing required envelope schema: {envelope_path}")
        envelope_obj = _load_json(envelope_path)
        cls.registry = cls.registry.with_resource(
            envelope_obj["$id"], Resource.from_contents(envelope_obj)
        )

    def test_all_50_realm_fixture_directories_exist(self):
        """All 50 realm directories must exist under fixtures/realms/ and contain a .md file."""
        self.assertEqual(len(_REQUIRED_REALMS), 50)
        self.assertTrue(_FIXTURES_DIR.exists(), f"Fixtures directory {_FIXTURES_DIR} missing")

        for prefix in _REQUIRED_REALMS:
            with self.subTest(realm=prefix):
                realm_dir = _FIXTURES_DIR / prefix
                self.assertTrue(realm_dir.is_dir(), f"Missing directory: {realm_dir}")
                md_files = list(realm_dir.glob("*.md"))
                self.assertGreaterEqual(
                    len(md_files), 1, f"No .md fixture found in {realm_dir}"
                )

    def test_all_50_fixtures_have_valid_frontmatter_and_markdown(self):
        """Each fixture must contain valid YAML frontmatter and a non-empty markdown body."""
        for prefix in _REQUIRED_REALMS:
            with self.subTest(realm=prefix):
                realm_dir = _FIXTURES_DIR / prefix
                fixture_path = next(realm_dir.glob("*.md"))
                raw_text = fixture_path.read_text(encoding="utf-8")

                frontmatter_text, body_text = _extract_frontmatter_and_body(raw_text)
                self.assertGreater(len(frontmatter_text.strip()), 0, "Empty frontmatter")
                self.assertGreater(len(body_text.strip()), 0, "Empty markdown body")

                parsed = yaml.safe_load(frontmatter_text)
                self.assertIsInstance(parsed, dict, "Frontmatter must parse to a dict")

                # Verify markdown headings and transclusions
                self.assertTrue(
                    _HEADING_PATTERN.search(body_text),
                    f"{prefix}: markdown body must contain at least one heading (# ...)",
                )
                self.assertTrue(
                    _TRANSCLUSION_PATTERN.search(body_text),
                    f"{prefix}: markdown body must contain at least one transclusion (![[...]])",
                )

    def test_all_50_fixtures_pkm_envelope(self):
        """Every fixture must declare a valid $pkm envelope with UUIDv7, realm, timestamps, and relations."""
        for prefix in _REQUIRED_REALMS:
            with self.subTest(realm=prefix):
                expected_realm = prefix.split("-", 1)[1]
                realm_dir = _FIXTURES_DIR / prefix
                fixture_path = next(realm_dir.glob("*.md"))
                raw_text = fixture_path.read_text(encoding="utf-8")

                frontmatter_text, _ = _extract_frontmatter_and_body(raw_text)
                data = yaml.safe_load(frontmatter_text)

                self.assertIn("$pkm", data, f"{prefix}: missing $pkm envelope")
                pkm = data["$pkm"]
                self.assertIsInstance(pkm, dict, f"{prefix}: $pkm must be a dictionary")

                # Verify id is a UUIDv7 URN
                self.assertIn("id", pkm, f"{prefix}: missing $pkm.id")
                match = _UUID_URN_PATTERN.match(pkm["id"])
                self.assertIsNotNone(match, f"{prefix}: $pkm.id '{pkm['id']}' not a valid UUID URN")
                raw_uuid = match.group(1)
                parsed_uuid = uuid.UUID(raw_uuid)
                self.assertEqual(
                    parsed_uuid.version, 7, f"{prefix}: $pkm.id must be a UUIDv7, got v{parsed_uuid.version}"
                )

                # Verify canonical realm name
                self.assertIn("realm", pkm, f"{prefix}: missing $pkm.realm")
                self.assertEqual(
                    pkm["realm"], expected_realm,
                    f"{prefix}: expected realm {expected_realm!r}, got {pkm['realm']!r}"
                )

                # Verify ISO timestamps
                self.assertIn("created_at", pkm, f"{prefix}: missing $pkm.created_at")
                self.assertTrue(
                    _ISO_TIMESTAMP_PATTERN.match(str(pkm["created_at"])),
                    f"{prefix}: invalid created_at timestamp: {pkm['created_at']}"
                )
                self.assertIn("updated_at", pkm, f"{prefix}: missing $pkm.updated_at")
                self.assertTrue(
                    _ISO_TIMESTAMP_PATTERN.match(str(pkm["updated_at"])),
                    f"{prefix}: invalid updated_at timestamp: {pkm['updated_at']}"
                )

                # Verify relations
                self.assertIn("relations", pkm, f"{prefix}: missing $pkm.relations")
                relations = pkm["relations"]
                self.assertIsInstance(relations, dict, f"{prefix}: relations must be a dict")
                self.assertGreater(len(relations), 0, f"{prefix}: relations dict must not be empty")
                for verb, target in relations.items():
                    targets = target if isinstance(target, list) else [target]
                    for t in targets:
                        self.assertTrue(
                            _VALID_URN_PATTERN.match(t),
                            f"{prefix}: relation target '{t}' for verb '{verb}' is not a valid URN"
                        )

    def test_all_50_fixtures_validate_against_schema(self):
        """Every fixture frontmatter must validate cleanly against its realm schema."""
        for prefix in _REQUIRED_REALMS:
            with self.subTest(realm=prefix):
                schema_path = _SCHEMAS_DIR / "v1" / "realms" / f"{prefix}.schema.json"
                self.assertTrue(schema_path.exists(), f"Missing schema for {prefix}: {schema_path}")
                schema_obj = _load_json(schema_path)

                realm_dir = _FIXTURES_DIR / prefix
                fixture_path = next(realm_dir.glob("*.md"))
                raw_text = fixture_path.read_text(encoding="utf-8")

                frontmatter_text, _ = _extract_frontmatter_and_body(raw_text)
                data = yaml.safe_load(frontmatter_text)

                validator = Draft202012Validator(schema_obj, registry=self.registry)
                try:
                    validator.validate(data)
                except jsonschema.ValidationError as exc:
                    self.fail(
                        f"Fixture for {prefix} ({fixture_path.name}) failed validation: {exc.message}\n"
                        f"Failed path: {list(exc.path)}\n"
                        f"Schema path: {list(exc.schema_path)}"
                    )


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAllRealmFixtures)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
