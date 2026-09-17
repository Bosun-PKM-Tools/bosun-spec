"""tests/test_templates.py
──────────────────────────
Validates all 50 canonical realm starter templates under templates/realms/:

  1. Verifies that all 50 realm template files exist (01-bosun through 50-relay).
  2. Verifies that standard mustache/jinja variables ({{ uuidv7 }}, {{ date_utc }}, {{ title }})
     are present in each template.
  3. Renders the template with mock variables and validates the parsed YAML frontmatter
     against schemas/v1/realms/<realm>.schema.json via Draft 2020-12 with archetype resolution.
  4. Verifies the markdown body contains # {{ title }} and standard starter headings.
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest
import yaml

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_TEMPLATES_DIR = _REPO_ROOT / "templates" / "realms"

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


class TestRealmTemplates(unittest.TestCase):
    def setUp(self):
        self.assertTrue(_TEMPLATES_DIR.exists(), f"Templates dir not found: {_TEMPLATES_DIR}")

    def test_all_50_template_files_exist(self):
        """All 50 realm template files must exist."""
        found_files = list(_TEMPLATES_DIR.glob("*.template.md"))
        self.assertEqual(len(found_files), 50, f"Expected 50 template files, found {len(found_files)}")
        for realm in _REQUIRED_REALMS:
            with self.subTest(realm=realm):
                template_file = _TEMPLATES_DIR / f"{realm}.template.md"
                self.assertTrue(template_file.exists(), f"Missing template file: {template_file.name}")

    def test_templates_declare_standard_mustache_variables(self):
        """All templates must contain standard mustache/jinja variables: {{ uuidv7 }}, {{ date_utc }}, {{ title }}."""
        for realm in _REQUIRED_REALMS:
            with self.subTest(realm=realm):
                template_file = _TEMPLATES_DIR / f"{realm}.template.md"
                content = template_file.read_text(encoding="utf-8")
                self.assertIn("{{ uuidv7 }}", content, f"{realm}: missing {{{{ uuidv7 }}}}")
                self.assertIn("{{ date_utc }}", content, f"{realm}: missing {{{{ date_utc }}}}")
                self.assertIn("{{ title }}", content, f"{realm}: missing {{{{ title }}}}")

    def test_templates_body_structure(self):
        """Templates must have a frontmatter block, '# {{ title }}', and starter headings."""
        for realm in _REQUIRED_REALMS:
            with self.subTest(realm=realm):
                template_file = _TEMPLATES_DIR / f"{realm}.template.md"
                content = template_file.read_text(encoding="utf-8")
                parts = content.split("---", 2)
                self.assertEqual(len(parts), 3, f"{realm}: invalid YAML frontmatter delimiters")
                body = parts[2].strip()
                self.assertTrue(body.startswith("# {{ title }}"), f"{realm}: body does not start with '# {{{{ title }}}}'")
                h2_headings = [line for line in body.splitlines() if line.startswith("## ")]
                self.assertGreaterEqual(len(h2_headings), 2, f"{realm}: expected at least 2 '## ' headings, got {len(h2_headings)}")

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_rendered_templates_validate_against_schema(self):
        """When rendered with sample values, each template's frontmatter validates against its realm schema."""
        # Build referencing Registry with archetypes and envelope
        registry = Registry()
        for arch_rel in _REQUIRED_ARCHETYPE_SCHEMAS:
            arch_obj = json.loads((_SCHEMAS_DIR / arch_rel).read_text(encoding="utf-8"))
            registry = registry.with_resource(arch_obj["$id"], Resource.from_contents(arch_obj))

        envelope_path = _SCHEMAS_DIR / "v1" / "meta" / "envelope.schema.json"
        if envelope_path.exists():
            env_obj = json.loads(envelope_path.read_text(encoding="utf-8"))
            registry = registry.with_resource(env_obj["$id"], Resource.from_contents(env_obj))

        mock_uuid = "018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
        mock_date = "2026-09-17T00:00:00Z"
        mock_title = "Canonical Template Spec"

        for realm in _REQUIRED_REALMS:
            with self.subTest(realm=realm):
                template_file = _TEMPLATES_DIR / f"{realm}.template.md"
                raw_content = template_file.read_text(encoding="utf-8")

                # Substitute template variables
                rendered = (
                    raw_content
                    .replace("{{ uuidv7 }}", mock_uuid)
                    .replace("{{ date_utc }}", mock_date)
                    .replace("{{ title }}", mock_title)
                )

                parts = rendered.split("---", 2)
                fm_data = yaml.safe_load(parts[1])

                schema_file = _SCHEMAS_DIR / "v1" / "realms" / f"{realm}.schema.json"
                schema_obj = json.loads(schema_file.read_text(encoding="utf-8"))

                validator = Draft202012Validator(schema_obj, registry=registry)
                validator.validate(fm_data)


if __name__ == "__main__":
    unittest.main()
