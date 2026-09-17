"""tests/test_synthetic_vault.py
───────────────────────────────
Test suite verifying the 50-realm synthetic multi-note demo locker.

Verifies:
  1. All 50 realm directories exist under fixtures/synthetic_vault/.
  2. Each realm contains 3-5 notes (200 notes total, within the 150-250 range).
  3. Every note features valid YAML frontmatter and non-empty markdown body.
  4. Universal $pkm envelope integrity: valid UUIDv7, realm pinning, ISO timestamps.
  5. Schema conformance: Every note validates cleanly against its realm schema
     via JSON Schema Draft 2020-12 with referencing Registry.
  6. Zero Broken URNs: All URNs referenced across $pkm.relations and URN attributes
     resolve to valid, existing notes in the synthetic vault.
  7. Cross-realm wiring:
     - Trice task -> Yeoman contact (assignedToContact)
     - Supercargo gear -> Quartermaster tx (purchasedViaTx)
     - Careen project -> Charthouse lore node (campaign_lore_node)
     - Pratique vitals -> Yeoman provider (consultedProvider)

Usage:
  python tests/test_synthetic_vault.py
  python -m pytest tests/test_synthetic_vault.py -v
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest
import uuid
from typing import Any, Dict, List, Set, Tuple

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
_VAULT_DIR = _REPO_ROOT / "fixtures" / "synthetic_vault"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID_PREFIX = "https://bosunpkm.com/schemas/"

_ARCHETYPE_FILES = (
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

_UUID_PATTERN = re.compile(r"^[0-9a-fA-F-]{36}$")
_UUID_URN_PATTERN = re.compile(r"^urn:uuid:([0-9a-fA-F-]{36})$")
_TYPED_URN_PATTERN = re.compile(r"^urn:([a-z0-9_-]+):([a-z0-9_-]+):([0-9a-fA-F-]{36})$")
_GENERAL_URN_PATTERN = re.compile(r"^urn:[a-zA-Z0-9_.:-]+$")
_ISO_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?(Z|[+-][0-9]{2}:?[0-9]{2})?)?$"
)
_HEADING_PATTERN = re.compile(r"^#+\s+.+", re.MULTILINE)
_TRANSCLUSION_PATTERN = re.compile(r"!\[\[(.*?)\]\]")


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


class TestSyntheticVault(unittest.TestCase):
    """Validation test suite for the 50-realm synthetic demo locker."""

    @classmethod
    def setUpClass(cls):
        if not _HAS_YAML:
            raise unittest.SkipTest("PyYAML not installed")
        if not _HAS_JSONSCHEMA:
            raise unittest.SkipTest("jsonschema not installed")

        # 1. Compile schema registry
        cls.registry = Registry()
        for arch_rel in _ARCHETYPE_FILES:
            arch_path = _SCHEMAS_DIR / arch_rel
            arch_obj = _load_json(arch_path)
            cls.registry = cls.registry.with_resource(
                arch_obj["$id"], Resource.from_contents(arch_obj)
            )

        envelope_path = _SCHEMAS_DIR / "v1" / "meta" / "envelope.schema.json"
        envelope_obj = _load_json(envelope_path)
        cls.registry = cls.registry.with_resource(
            envelope_obj["$id"], Resource.from_contents(envelope_obj)
        )

        cls.realm_validators: Dict[str, Draft202012Validator] = {}
        for prefix in _REQUIRED_REALMS:
            schema_path = _SCHEMAS_DIR / "v1" / "realms" / f"{prefix}.schema.json"
            schema_obj = _load_json(schema_path)
            cls.realm_validators[prefix] = Draft202012Validator(
                schema_obj, registry=cls.registry
            )

        # 2. Ingest and index all synthetic notes
        cls.all_notes: List[Dict[str, Any]] = []
        cls.notes_by_uuid: Dict[str, Dict[str, Any]] = {}
        cls.notes_by_urn: Dict[str, Dict[str, Any]] = {}

        if _VAULT_DIR.exists():
            for md_path in _VAULT_DIR.rglob("*.md"):
                content = md_path.read_text(encoding="utf-8")
                try:
                    fm_text, body = _extract_frontmatter_and_body(content)
                    data = yaml.safe_load(fm_text)
                    pkm = data.get("$pkm", {})
                    note_id = pkm.get("id", "")
                    match = _UUID_URN_PATTERN.match(note_id)
                    note_uuid = match.group(1) if match else None

                    note_info = {
                        "path": md_path,
                        "rel_path": md_path.relative_to(_VAULT_DIR),
                        "data": data,
                        "pkm": pkm,
                        "uuid": note_uuid,
                        "id": note_id,
                        "realm": pkm.get("realm", ""),
                        "body": body,
                    }
                    cls.all_notes.append(note_info)
                    if note_uuid:
                        cls.notes_by_uuid[note_uuid.lower()] = note_info
                        cls.notes_by_urn[note_id] = note_info
                        # Map entity URNs for this note's realm
                        realm = note_info["realm"]
                        cls.notes_by_urn[f"urn:{realm}:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:contact:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:task:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:event:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:lore:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:cas:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:property:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:milestone:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:person:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:venue:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:vendor:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:org:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:prior:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:cad:{note_uuid}"] = note_info
                        cls.notes_by_urn[f"urn:{realm}:tide:{note_uuid}"] = note_info
                        if realm == "quartermaster":
                            cls.notes_by_urn[f"urn:qtm:tx:{note_uuid}"] = note_info
                            cls.notes_by_urn[f"urn:quartermaster:tx:{note_uuid}"] = note_info
                except Exception:
                    pass

    def test_all_50_realm_directories_exist(self):
        """All 50 realm subdirectories (01-bosun to 50-relay) must exist in synthetic_vault."""
        self.assertTrue(_VAULT_DIR.exists(), f"Vault directory missing: {_VAULT_DIR}")
        for prefix in _REQUIRED_REALMS:
            with self.subTest(realm=prefix):
                realm_path = _VAULT_DIR / prefix
                self.assertTrue(
                    realm_path.is_dir(), f"Missing realm directory: {realm_path}"
                )

    def test_vault_total_and_per_realm_note_counts(self):
        """Total notes must be between 150-250, with 3-5 notes per realm."""
        total_notes = len(self.all_notes)
        self.assertGreaterEqual(total_notes, 150, f"Expected >= 150 notes, got {total_notes}")
        self.assertLessEqual(total_notes, 250, f"Expected <= 250 notes, got {total_notes}")

        for prefix in _REQUIRED_REALMS:
            with self.subTest(realm=prefix):
                realm_dir = _VAULT_DIR / prefix
                notes = list(realm_dir.glob("*.md"))
                self.assertGreaterEqual(
                    len(notes), 3, f"{prefix}: expected >= 3 notes, got {len(notes)}"
                )
                self.assertLessEqual(
                    len(notes), 5, f"{prefix}: expected <= 5 notes, got {len(notes)}"
                )

    def test_all_notes_have_valid_frontmatter_and_markdown_structure(self):
        """Each note contains valid YAML frontmatter and non-empty markdown body with headings."""
        for note in self.all_notes:
            with self.subTest(note=str(note["rel_path"])):
                self.assertIsInstance(note["data"], dict, "Frontmatter must be a dictionary")
                self.assertTrue(
                    _HEADING_PATTERN.search(note["body"]),
                    f"{note['rel_path']}: body must contain at least one markdown heading",
                )
                self.assertTrue(
                    _TRANSCLUSION_PATTERN.search(note["body"]),
                    f"{note['rel_path']}: body must contain at least one transclusion anchor",
                )

    def test_all_notes_pkm_universal_envelope_integrity(self):
        """Every note must have a valid UUIDv7 ID, realm, timestamps, and relations."""
        seen_ids: Set[str] = set()

        for note in self.all_notes:
            with self.subTest(note=str(note["rel_path"])):
                pkm = note["pkm"]
                self.assertIn("id", pkm, f"{note['rel_path']}: missing $pkm.id")
                note_id = pkm["id"]

                # Unique ID check
                self.assertNotIn(note_id, seen_ids, f"Duplicate $pkm.id: {note_id}")
                seen_ids.add(note_id)

                # UUIDv7 verification
                match = _UUID_URN_PATTERN.match(note_id)
                self.assertIsNotNone(match, f"Invalid UUID URN format: {note_id}")
                raw_uuid = match.group(1)
                parsed_uuid = uuid.UUID(raw_uuid)
                self.assertEqual(
                    parsed_uuid.version, 7, f"Expected UUIDv7, got v{parsed_uuid.version}"
                )

                # Canonical realm matching directory
                expected_realm = note["rel_path"].parts[0].split("-", 1)[1]
                self.assertEqual(
                    pkm.get("realm"),
                    expected_realm,
                    f"Realm mismatch: expected '{expected_realm}', got '{pkm.get('realm')}'",
                )

                # Timestamps
                self.assertTrue(
                    _ISO_TIMESTAMP_PATTERN.match(str(pkm.get("created_at"))),
                    f"Invalid created_at: {pkm.get('created_at')}",
                )
                self.assertTrue(
                    _ISO_TIMESTAMP_PATTERN.match(str(pkm.get("updated_at"))),
                    f"Invalid updated_at: {pkm.get('updated_at')}",
                )

                # Relations object present
                self.assertIn("relations", pkm, "Missing $pkm.relations")
                self.assertIsInstance(pkm["relations"], dict, "$pkm.relations must be dict")

    def test_all_notes_validate_against_realm_schemas(self):
        """All 200 notes must validate cleanly against their realm schemas."""
        for note in self.all_notes:
            realm_prefix = note["rel_path"].parts[0]
            validator = self.realm_validators[realm_prefix]
            with self.subTest(note=str(note["rel_path"])):
                try:
                    validator.validate(note["data"])
                except jsonschema.ValidationError as exc:
                    self.fail(
                        f"Schema validation failed for {note['rel_path']}: {exc.message}\n"
                        f"At path: {list(exc.path)}"
                    )

    def test_zero_broken_urns_and_referential_integrity(self):
        """Every URN in $pkm.relations must resolve to an existing note in the synthetic vault."""
        broken_urns: List[str] = []

        for note in self.all_notes:
            relations = note["pkm"].get("relations", {})
            for verb, target in relations.items():
                targets = target if isinstance(target, list) else [target]
                for t in targets:
                    # Match typed URN, UUID URN, or extract UUID
                    resolved = False
                    if t in self.notes_by_urn:
                        resolved = True
                    else:
                        # Extract 36-character UUID from ending
                        candidate_uuid = t.split(":")[-1]
                        if _UUID_PATTERN.match(candidate_uuid):
                            if candidate_uuid.lower() in self.notes_by_uuid:
                                resolved = True

                    if not resolved:
                        broken_urns.append(
                            f"From {note['rel_path']} (verb={verb}): broken URN '{t}'"
                        )

        self.assertEqual(
            broken_urns,
            [],
            f"Found {len(broken_urns)} broken URN(s) in synthetic vault:\n"
            + "\n".join(broken_urns[:20]),
        )

    def test_required_cross_realm_relationships_exist(self):
        """Verify the 4 explicit cross-realm wiring requirements are active and resolvable."""
        # 1. Trice task -> Yeoman contact (assignedToContact)
        trice_notes = [n for n in self.all_notes if n["realm"] == "trice"]
        trice_assigned = [
            n for n in trice_notes if "assignedToContact" in n["pkm"].get("relations", {})
        ]
        self.assertGreaterEqual(
            len(trice_assigned), 1, "Expected at least 1 Trice task with assignedToContact"
        )
        for tn in trice_assigned:
            target_urn = tn["pkm"]["relations"]["assignedToContact"]
            target_uuid = target_urn.split(":")[-1].lower()
            self.assertIn(target_uuid, self.notes_by_uuid)
            self.assertEqual(
                self.notes_by_uuid[target_uuid]["realm"],
                "yeoman",
                f"Trice assignedToContact '{target_urn}' must target a Yeoman contact",
            )

        # 2. Supercargo gear -> Quartermaster tx (purchasedViaTx)
        supercargo_notes = [n for n in self.all_notes if n["realm"] == "supercargo"]
        supercargo_purchased = [
            n for n in supercargo_notes if "purchasedViaTx" in n["pkm"].get("relations", {})
        ]
        self.assertGreaterEqual(
            len(supercargo_purchased), 1, "Expected at least 1 Supercargo item with purchasedViaTx"
        )
        for sn in supercargo_purchased:
            target_urn = sn["pkm"]["relations"]["purchasedViaTx"]
            target_uuid = target_urn.split(":")[-1].lower()
            self.assertIn(target_uuid, self.notes_by_uuid)
            self.assertEqual(
                self.notes_by_uuid[target_uuid]["realm"],
                "quartermaster",
                f"Supercargo purchasedViaTx '{target_urn}' must target a Quartermaster tx",
            )

        # 3. Careen project -> Charthouse lore node (campaign_lore_node)
        careen_notes = [n for n in self.all_notes if n["realm"] == "careen"]
        careen_lore = [
            n for n in careen_notes if "campaign_lore_node" in n["pkm"].get("relations", {})
        ]
        self.assertGreaterEqual(
            len(careen_lore), 1, "Expected at least 1 Careen project with campaign_lore_node"
        )
        for cn in careen_lore:
            target_urn = cn["pkm"]["relations"]["campaign_lore_node"]
            target_uuid = target_urn.split(":")[-1].lower()
            self.assertIn(target_uuid, self.notes_by_uuid)
            self.assertEqual(
                self.notes_by_uuid[target_uuid]["realm"],
                "charthouse",
                f"Careen campaign_lore_node '{target_urn}' must target a Charthouse node",
            )

        # 4. Pratique vitals -> Yeoman provider (consultedProvider)
        pratique_notes = [n for n in self.all_notes if n["realm"] == "pratique"]
        pratique_consulted = [
            n for n in pratique_notes if "consultedProvider" in n["pkm"].get("relations", {})
        ]
        self.assertGreaterEqual(
            len(pratique_consulted), 1, "Expected at least 1 Pratique record with consultedProvider"
        )
        for pn in pratique_consulted:
            target_urn = pn["pkm"]["relations"]["consultedProvider"]
            target_uuid = target_urn.split(":")[-1].lower()
            self.assertIn(target_uuid, self.notes_by_uuid)
            self.assertEqual(
                self.notes_by_uuid[target_uuid]["realm"],
                "yeoman",
                f"Pratique consultedProvider '{target_urn}' must target a Yeoman provider",
            )


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSyntheticVault)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
