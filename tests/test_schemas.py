"""
tests/test_schemas.py
─────────────────────
Validates that every JSON schema file in bosun-spec/schemas/ (recursively) is:

  1. Parseable as valid JSON (no syntax errors, no trailing commas, etc.)
  2. Declares a recognised ``$schema`` URI (meta-schema present).
  3. Internally well-formed per ``jsonschema.check_schema()`` — i.e. the
     schema itself satisfies the JSON Schema Draft 2020-12 meta-schema.
  4. Nested ``*.schema.json`` files under ``schemas/v1/`` are discovered
     recursively and must declare Draft 2020-12.

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
    from referencing import Registry, Resource
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

# Locate the schemas/ directory relative to this file's parent (repo root)
_REPO_ROOT = pathlib.Path(__file__).parent.parent
_SCHEMAS_DIR = _REPO_ROOT / "schemas"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID_PREFIX = "https://bosunpkm.com/schemas/"

# Known JSON Schema draft URIs we accept
_KNOWN_DRAFTS = {
    _DRAFT_2020_12,
    "https://json-schema.org/draft/2019-09/schema",
    "http://json-schema.org/draft-07/schema#",
    "http://json-schema.org/draft-06/schema#",
    "http://json-schema.org/draft-04/schema#",
}

# 5 Archetype Base Schemas
_REQUIRED_ARCHETYPE_SCHEMAS = (
    "v1/archetypes/catalog-dossier.schema.json",
    "v1/archetypes/interaction-ledger.schema.json",
    "v1/archetypes/dual-track-telemetry.schema.json",
    "v1/archetypes/stage-gate-manifest.schema.json",
    "v1/archetypes/sovereign-vault.schema.json",
)

# 50 Realm Delta Schemas (01-50)
_REQUIRED_REALM_SCHEMAS = (
    "v1/realms/01-bosun.schema.json",
    "v1/realms/02-yeoman.schema.json",
    "v1/realms/03-trice.schema.json",
    "v1/realms/04-logbook.schema.json",
    "v1/realms/05-quartermaster.schema.json",
    "v1/realms/06-harbor.schema.json",
    "v1/realms/07-press.schema.json",
    "v1/realms/08-embers.schema.json",
    "v1/realms/09-careen.schema.json",
    "v1/realms/10-primer.schema.json",
    "v1/realms/11-passage.schema.json",
    "v1/realms/12-galley.schema.json",
    "v1/realms/13-pratique.schema.json",
    "v1/realms/14-tactician.schema.json",
    "v1/realms/15-drydock.schema.json",
    "v1/realms/16-squadron.schema.json",
    "v1/realms/17-supercargo.schema.json",
    "v1/realms/18-commonplace.schema.json",
    "v1/realms/19-chantey.schema.json",
    "v1/realms/20-marquee.schema.json",
    "v1/realms/21-scrimshaw.schema.json",
    "v1/realms/22-traverse.schema.json",
    "v1/realms/23-docent.schema.json",
    "v1/realms/24-proctor.schema.json",
    "v1/realms/25-ropewalk.schema.json",
    "v1/realms/26-gavel.schema.json",
    "v1/realms/27-lineage.schema.json",
    "v1/realms/28-legacy.schema.json",
    "v1/realms/29-arbor.schema.json",
    "v1/realms/30-the-glass.schema.json",
    "v1/realms/31-dispatch.schema.json",
    "v1/realms/32-registry.schema.json",
    "v1/realms/33-purser.schema.json",
    "v1/realms/34-cadence.schema.json",
    "v1/realms/35-reckoning.schema.json",
    "v1/realms/36-strongbox.schema.json",
    "v1/realms/37-trajectory.schema.json",
    "v1/realms/38-binnacle.schema.json",
    "v1/realms/39-claim.schema.json",
    "v1/realms/40-tribute.schema.json",
    "v1/realms/41-weft.schema.json",
    "v1/realms/42-reverie.schema.json",
    "v1/realms/43-provenance.schema.json",
    "v1/realms/44-menagerie.schema.json",
    "v1/realms/45-muster.schema.json",
    "v1/realms/46-breadboard.schema.json",
    "v1/realms/47-pavilion.schema.json",
    "v1/realms/48-charthouse.schema.json",
    "v1/realms/49-commonwealth.schema.json",
    "v1/realms/50-relay.schema.json",
)

# Realm v1 contracts that must exist as nested Draft 2020-12 schema files.
_REQUIRED_V1_SCHEMAS = (
    "v1/trice/task.schema.json",
    "v1/trice/project.schema.json",
    "v1/logbook/journal.schema.json",
    "v1/logbook/event.schema.json",
    "v1/yeoman/contact.schema.json",
    "v1/yeoman/interaction.schema.json",
    "v1/commonplace/work.schema.json",
    "v1/relations/relations.schema.json",
    "v1/meta/envelope.schema.json",
    *_REQUIRED_ARCHETYPE_SCHEMAS,
    *_REQUIRED_REALM_SCHEMAS,
)


def _relative_schema_name(path):
    """Return a stable POSIX-relative path from schemas/ for test names."""
    return path.relative_to(_SCHEMAS_DIR).as_posix()


def _collect_schemas():
    """Return a list of (relative_name, path) tuples for all .json files under schemas/.

    Recurses into realm subdirectories so ``*.schema.json`` files nested under
    ``schemas/v1/<realm>/`` are discovered alongside the top-level v0.1 contracts.
    """
    if not _SCHEMAS_DIR.exists():
        return []
    return sorted(
        (_relative_schema_name(p), p)
        for p in _SCHEMAS_DIR.rglob("*.json")
        if p.is_file()
    )


def _collect_schema_json():
    """Return (relative_name, path) tuples for nested ``*.schema.json`` files."""
    return [
        (name, path)
        for name, path in _collect_schemas()
        if name.endswith(".schema.json")
    ]


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
                f"{path.relative_to(_SCHEMAS_DIR).as_posix()} contains invalid JSON: {exc}"
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
                        f"{name}: failed Draft 2020-12 meta-schema validation: {exc.message}"
                    )
                except Exception as exc:  # noqa: BLE001
                    self.fail(
                        f"{name}: unexpected error during check_schema: {exc}"
                    )

    def test_schema_json_files_are_discovered_recursively(self):
        """Nested ``*.schema.json`` files under schemas/v1/ must be collected."""
        discovered = {name for name, _path in _collect_schema_json()}
        missing = [name for name in _REQUIRED_V1_SCHEMAS if name not in discovered]
        self.assertEqual(
            missing,
            [],
            "Required v1 *.schema.json files were not discovered recursively: "
            f"{missing}"
        )
        for name in discovered:
            with self.subTest(schema=name):
                self.assertIn(
                    "/",
                    name,
                    f"{name}: expected a nested path under schemas/v1/<realm>/"
                )

    def test_v1_schema_json_files_declare_draft_2020_12(self):
        """Every nested ``*.schema.json`` must pin JSON Schema Draft 2020-12."""
        schema_json = _collect_schema_json()
        self.assertGreater(
            len(schema_json),
            0,
            "No *.schema.json files found under schemas/; "
            "v1 realm contracts are missing"
        )
        for name, path in schema_json:
            with self.subTest(schema=name):
                obj = self._load_json(path)
                self.assertEqual(
                    obj.get("$schema"),
                    _DRAFT_2020_12,
                    f"{name}: $schema must be {_DRAFT_2020_12!r}, "
                    f"got {obj.get('$schema')!r}"
                )

    def test_all_schema_ids_are_unique(self):
        """Canonical $id URIs must be unique across the schemas/ tree."""
        seen = {}
        for name, path in self.schemas:
            obj = self._load_json(path)
            schema_id = obj.get("$id")
            if not schema_id:
                continue
            with self.subTest(schema=name):
                self.assertNotIn(
                    schema_id,
                    seen,
                    f"{name}: duplicate $id {schema_id!r} "
                    f"(already used by {seen.get(schema_id)})"
                )
            seen[schema_id] = name

    def test_schema_ids_match_canonical_path(self):
        """$id URIs follow https://bosunpkm.com/schemas/<relative-path>."""
        for name, path in self.schemas:
            with self.subTest(schema=name):
                obj = self._load_json(path)
                expected = _CANONICAL_ID_PREFIX + name
                self.assertEqual(
                    obj.get("$id"),
                    expected,
                    f"{name}: $id must be {expected!r}, got {obj.get('$id')!r}"
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

    def test_all_5_archetypes_exist_and_pin_canonical_id(self):
        """All 5 archetype base schemas must exist, pin Draft 2020-12 and canonical $id."""
        for rel_path in _REQUIRED_ARCHETYPE_SCHEMAS:
            with self.subTest(archetype=rel_path):
                schema_path = _SCHEMAS_DIR / rel_path
                self.assertTrue(schema_path.exists(), f"Missing archetype schema: {rel_path}")
                obj = self._load_json(schema_path)
                self.assertEqual(obj.get("$schema"), _DRAFT_2020_12)
                expected_id = _CANONICAL_ID_PREFIX + rel_path
                self.assertEqual(obj.get("$id"), expected_id)
                self.assertIn("$pkm", obj.get("required", []))
                self.assertIn("$defs", obj)
                self.assertIn("pkmEnvelope", obj["$defs"])
                pkm = obj["$defs"]["pkmEnvelope"]
                self.assertEqual(
                    set(pkm.get("required", [])),
                    {"id", "realm", "created_at", "updated_at"}
                )

    def test_all_50_realm_schemas_exist_and_pin_canonical_id(self):
        """All 50 realm schemas must exist, pin Draft 2020-12 and canonical $id."""
        self.assertEqual(len(_REQUIRED_REALM_SCHEMAS), 50)
        for rel_path in _REQUIRED_REALM_SCHEMAS:
            with self.subTest(realm=rel_path):
                schema_path = _SCHEMAS_DIR / rel_path
                self.assertTrue(schema_path.exists(), f"Missing realm schema: {rel_path}")
                obj = self._load_json(schema_path)
                self.assertEqual(obj.get("$schema"), _DRAFT_2020_12)
                expected_id = _CANONICAL_ID_PREFIX + rel_path
                self.assertEqual(obj.get("$id"), expected_id)

    def test_all_50_realm_schemas_extend_archetypes_and_declare_attributes(self):
        """Each realm schema extends its archetype via allOf and defines its unique delta attributes."""
        expected_meta = {
            "01-bosun": ("stage-gate-manifest.schema.json", "bosun", ["zettel_type", "wikilinks", "ast_version"]),
            "02-yeoman": ("interaction-ledger.schema.json", "yeoman", ["cadence_days", "channels", "last_contact_date"]),
            "03-trice": ("stage-gate-manifest.schema.json", "trice", ["task_state", "priority", "recurrence_rule"]),
            "04-logbook": ("interaction-ledger.schema.json", "logbook", ["journal_date", "agenda_blocks", "transclusion_anchors"]),
            "05-quartermaster": ("sovereign-vault.schema.json", "quartermaster", ["beancount_account", "tx_hash", "currency_code"]),
            "06-harbor": ("catalog-dossier.schema.json", "harbor", ["slug", "edge_route", "render_template"]),
            "07-press": ("catalog-dossier.schema.json", "press", ["sku", "vector_asset_cas", "cut_sheet_spec"]),
            "08-embers": ("catalog-dossier.schema.json", "embers", ["exif_payload", "media_hash_sha256", "codec"]),
            "09-careen": ("stage-gate-manifest.schema.json", "careen", ["kanban_stage", "sprint_ref", "milestone_urn"]),
            "10-primer": ("stage-gate-manifest.schema.json", "primer", ["spaced_interval_days", "ease_factor", "skill_node"]),
            "11-passage": ("stage-gate-manifest.schema.json", "passage", ["transit_mode", "booking_ref", "waypoints"]),
            "12-galley": ("catalog-dossier.schema.json", "galley", ["servings", "prep_time_minutes", "ingredients_schema"]),
            "13-pratique": ("dual-track-telemetry.schema.json", "pratique", ["fhir_code", "sensor_source", "telemetry_parquet_ref"]),
            "14-tactician": ("dual-track-telemetry.schema.json", "tactician", ["sport_type", "split_metrics", "monte_carlo_preset"]),
            "15-drydock": ("dual-track-telemetry.schema.json", "drydock", ["property_urn", "deed_ref", "utility_metric_keys"]),
            "16-squadron": ("dual-track-telemetry.schema.json", "squadron", ["vin", "engine_hours", "telemetry_parquet_ref"]),
            "17-supercargo": ("catalog-dossier.schema.json", "supercargo", ["serial_number", "mac_address", "warranty_expiry"]),
            "18-commonplace": ("catalog-dossier.schema.json", "commonplace", ["isbn13", "creator", "shelf_state", "rating"]),
            "19-chantey": ("catalog-dossier.schema.json", "chantey", ["enclosure_url", "duration_seconds", "transcript_cas"]),
            "20-marquee": ("catalog-dossier.schema.json", "marquee", ["timecode_in", "timecode_out", "rush_bin"]),
            "21-scrimshaw": ("catalog-dossier.schema.json", "scrimshaw", ["cad_model_cas", "gcode_profile", "toolpath_version"]),
            "22-traverse": ("catalog-dossier.schema.json", "traverse", ["geojson_feature", "epsg_srid", "survey_datum"]),
            "23-docent": ("catalog-dossier.schema.json", "docent", ["doi", "bibtex_key", "arxiv_id"]),
            "24-proctor": ("sovereign-vault.schema.json", "proctor", ["docket_number", "pacer_case_id", "statute_refs"]),
            "25-ropewalk": ("sovereign-vault.schema.json", "ropewalk", ["repo_slug", "remote_origin", "dotfile_target_path"]),
            "26-gavel": ("interaction-ledger.schema.json", "gavel", ["committee_slug", "meeting_date", "bylaws_uri", "motion_tallies"]),
            "27-lineage": ("interaction-ledger.schema.json", "lineage", ["individual_urn", "pedigree_branch", "vital_dates", "gedcom_id"]),
            "28-legacy": ("sovereign-vault.schema.json", "legacy", ["trust_ref", "living_will_cas", "executor_contact_urn", "durable_poa_hash"]),
            "29-arbor": ("catalog-dossier.schema.json", "arbor", ["taxonomic_species", "seed_vintage_year", "planting_zone", "soil_ph_optimal"]),
            "30-the-glass": ("dual-track-telemetry.schema.json", "the-glass", ["station_id", "barometric_hpa", "tide_gauge_urn", "telemetry_parquet_ref"]),
            "31-dispatch": ("interaction-ledger.schema.json", "dispatch", ["sender_urn", "recipient_urn", "postmark_date", "courier_tracking"]),
            "32-registry": ("sovereign-vault.schema.json", "registry", ["document_type", "issuing_jurisdiction", "expiry_date", "encrypted_credential_cas"]),
            "33-purser": ("catalog-dossier.schema.json", "purser", ["billing_cadence", "vendor_urn", "monthly_spend_usd", "cancellation_sla"]),
            "34-cadence": ("stage-gate-manifest.schema.json", "cadence", ["streak_count_current", "target_frequency", "ritual_window", "best_streak"]),
            "35-reckoning": ("catalog-dossier.schema.json", "reckoning", ["decision_framework", "pre_mortem_risk_tags", "bias_audit_flags"]),
            "36-strongbox": ("sovereign-vault.schema.json", "strongbox", ["key_algorithm", "public_key_fingerprint", "hardware_token_serial", "derivation_path"]),
            "37-trajectory": ("catalog-dossier.schema.json", "trajectory", ["role_title", "organization_urn", "tenure_start", "case_study_slugs"]),
            "38-binnacle": ("catalog-dossier.schema.json", "binnacle", ["theological_tradition", "credo_axiom_key", "canonical_scripture_refs"]),
            "39-claim": ("catalog-dossier.schema.json", "claim", ["patent_number", "jurisdiction_office", "filing_date", "prior_art_urns"]),
            "40-tribute": ("interaction-ledger.schema.json", "tribute", ["recipient_contact_urn", "sizing_chart_profile", "reciprocity_balance"]),
            "41-weft": ("catalog-dossier.schema.json", "weft", ["garment_category", "textile_composition", "care_wash_spec", "tailoring_measurements"]),
            "42-reverie": ("interaction-ledger.schema.json", "reverie", ["dream_motif_tags", "lucidity_level", "sleep_stage_anchor"]),
            "43-provenance": ("catalog-dossier.schema.json", "provenance", ["appraisal_usd", "chain_of_custody_urns", "edition_number", "authenticity_cert_cas"]),
            "44-menagerie": ("interaction-ledger.schema.json", "menagerie", ["species_breed", "microchip_hex_id", "vet_clinic_urn", "vaccination_schedule"]),
            "45-muster": ("catalog-dossier.schema.json", "muster", ["rally_point_coordinates", "bug_out_tier", "ration_expiry_date", "comms_frequency_mhz"]),
            "46-breadboard": ("catalog-dossier.schema.json", "breadboard", ["schematic_cas", "pcb_revision", "gpio_pinout_map", "operating_voltage_vdc"]),
            "47-pavilion": ("stage-gate-manifest.schema.json", "pavilion", ["run_of_show_steps", "venue_reservation_urn", "headcount_target"]),
            "48-charthouse": ("stage-gate-manifest.schema.json", "charthouse", ["campaign_lore_node", "timeline_epoch", "scene_binder_ref"]),
            "49-commonwealth": ("interaction-ledger.schema.json", "commonwealth", ["initiative_name", "hours_logged", "volunteer_urn", "mutual_aid_batch_id"]),
            "50-relay": ("sovereign-vault.schema.json", "relay", ["dead_man_interval_days", "heartbeat_received_at", "master_recovery_key_cas"]),
        }

        for prefix, (arch_file, realm_name, delta_attrs) in expected_meta.items():
            with self.subTest(realm=prefix):
                schema_path = _SCHEMAS_DIR / "v1" / "realms" / f"{prefix}.schema.json"
                obj = self._load_json(schema_path)
                self.assertIn("allOf", obj, f"{prefix}: missing allOf composition")
                all_of = obj["allOf"]
                self.assertGreaterEqual(len(all_of), 2, f"{prefix}: allOf must include archetype ref and delta")

                # Verify archetype $ref
                expected_ref = f"{_CANONICAL_ID_PREFIX}v1/archetypes/{arch_file}"
                self.assertEqual(all_of[0].get("$ref"), expected_ref)

                # Verify envelope composition
                expected_envelope_ref = f"{_CANONICAL_ID_PREFIX}v1/meta/envelope.schema.json"
                self.assertTrue(
                    any(clause.get("$ref") == expected_envelope_ref for clause in all_of),
                    f"{prefix}: missing composition with envelope.schema.json"
                )

                # Verify delta properties
                delta = all_of[-1]
                props = delta.get("properties", {})
                for attr in delta_attrs:
                    self.assertIn(attr, props, f"{prefix}: missing delta attribute '{attr}'")

                # Verify realm const
                pkm_realm_const = (
                    props.get("$pkm", {})
                    .get("properties", {})
                    .get("realm", {})
                    .get("const")
                )
                self.assertEqual(
                    pkm_realm_const,
                    realm_name,
                    f"{prefix}: expected $pkm.realm const {realm_name!r}, got {pkm_realm_const!r}"
                )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_universal_envelope_postel_coercion_timestamps(self):
        """Universal envelope accepts full UTC, date-times missing seconds, and date-only strings."""
        arch_path = _SCHEMAS_DIR / "v1" / "archetypes" / "catalog-dossier.schema.json"
        obj = self._load_json(arch_path)
        envelope_schema = obj["$defs"]["pkmEnvelope"]
        validator = Draft202012Validator(envelope_schema)

        # Valid ISO timestamp variations under Postel coercion
        valid_timestamps = [
            "2026-09-16T12:00:00Z",       # Full UTC with seconds
            "2026-09-16T12:00:00.123Z",   # Full UTC with fractional seconds
            "2026-09-16T12:00Z",          # Missing seconds (permissive Postel coercion)
            "2026-09-16",                 # Date-only (permissive Postel coercion)
            "2026-09-16T14:30:00+02:00",  # UTC offset
        ]
        for ts in valid_timestamps:
            with self.subTest(timestamp=ts):
                sample = {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "harbor",
                    "created_at": ts,
                    "updated_at": ts,
                }
                validator.validate(sample)

        # Invalid timestamps must be rejected
        invalid_timestamps = ["not-a-date", "2026/09/16", "today"]
        for ts in invalid_timestamps:
            with self.subTest(invalid_timestamp=ts):
                sample = {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "harbor",
                    "created_at": ts,
                    "updated_at": ts,
                }
                with self.assertRaises(jsonschema.ValidationError):
                    validator.validate(sample)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_universal_envelope_id_uuidv7_urn(self):
        """Universal envelope requires a valid UUID URN for $pkm.id."""
        arch_path = _SCHEMAS_DIR / "v1" / "archetypes" / "catalog-dossier.schema.json"
        obj = self._load_json(arch_path)
        envelope_schema = obj["$defs"]["pkmEnvelope"]
        validator = Draft202012Validator(envelope_schema)

        # Valid UUIDv7 URN
        valid_sample = {
            "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "realm": "harbor",
            "created_at": "2026-09-16T12:00:00Z",
            "updated_at": "2026-09-16T12:00:00Z",
        }
        validator.validate(valid_sample)

        # Invalid IDs must be rejected
        invalid_ids = [
            "018f62f8-9a3b-7d23-bf72-5b9c03bfba43",  # Bare UUID without urn:uuid: prefix
            "urn:uuid:short-id",                       # Non-UUID length
            "urn:other:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
        ]
        for bad_id in invalid_ids:
            with self.subTest(bad_id=bad_id):
                bad_sample = dict(valid_sample, id=bad_id)
                with self.assertRaises(jsonschema.ValidationError):
                    validator.validate(bad_sample)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_all_50_realms_validate_sample_instances(self):
        """Validate sample payloads for all 25 realms against their delta schemas with archetype resolution."""
        # Build registry from all archetype schemas
        registry = Registry()
        for arch_rel in _REQUIRED_ARCHETYPE_SCHEMAS:
            arch_obj = self._load_json(_SCHEMAS_DIR / arch_rel)
            registry = registry.with_resource(arch_obj["$id"], Resource.from_contents(arch_obj))
        envelope_obj = self._load_json(_SCHEMAS_DIR / "v1/meta/envelope.schema.json")
        registry = registry.with_resource(envelope_obj["$id"], Resource.from_contents(envelope_obj))

        samples = {
            "01-bosun": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "bosun",
                    "created_at": "2026-09-16T12:00Z",
                    "updated_at": "2026-09-16T12:00:00Z",
                    "relations": {"wikilinksTo": ["urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba44"]}
                },
                "zettel_type": "concept",
                "wikilinks": ["[[Knowledge Graph]]"],
                "ast_version": "1.0.0"
            },
            "02-yeoman": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "yeoman",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T14:30:00Z"
                },
                "cadence_days": 14,
                "channels": [{"kind": "email", "value": "ada@example.org", "label": "work"}],
                "last_contact_date": "2026-09-16"
            },
            "03-trice": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "trice",
                    "created_at": "2026-09-16T10:00:00Z",
                    "updated_at": "2026-09-16T10:00:00Z"
                },
                "task_state": "active",
                "priority": "p1",
                "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO"
            },
            "04-logbook": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "logbook",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T23:59:59Z"
                },
                "journal_date": "2026-09-16",
                "agenda_blocks": [{"title": "Standup", "start": "2026-09-16T09:00:00Z"}],
                "transclusion_anchors": ["^daily-goals"]
            },
            "05-quartermaster": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "quartermaster",
                    "created_at": "2026-09-16T08:00:00Z",
                    "updated_at": "2026-09-16T08:00:00Z"
                },
                "beancount_account": "Assets:Bank:Checking",
                "tx_hash": "tx_abc123def456",
                "currency_code": "USD"
            },
            "06-harbor": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "harbor",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "slug": "getting-started",
                "edge_route": "/docs/intro",
                "render_template": "docs-page"
            },
            "07-press": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "press",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "sku": "PRESS-POSTER-001",
                "vector_asset_cas": "urn:press:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "cut_sheet_spec": {"width_mm": 420, "height_mm": 594}
            },
            "08-embers": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "embers",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "exif_payload": {"iso": 400, "focal_length": "50mm"},
                "media_hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "codec": "image/jpeg"
            },
            "09-careen": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "careen",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "kanban_stage": "in_progress",
                "sprint_ref": "sprint-2026-38",
                "milestone_urn": "urn:careen:milestone:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
            },
            "10-primer": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "primer",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "spaced_interval_days": 6.5,
                "ease_factor": 2.5,
                "skill_node": "algorithms.binary_search"
            },
            "11-passage": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "passage",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "transit_mode": "rail",
                "booking_ref": "PASS-8842-X",
                "waypoints": [{"name": "King's Cross", "coordinates": [-0.1246, 51.5308]}]
            },
            "12-galley": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "galley",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "servings": 4,
                "prep_time_minutes": 25,
                "ingredients_schema": [{"item": "Sea Salt", "amount": 5, "unit": "grams"}]
            },
            "13-pratique": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "pratique",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "fhir_code": "8867-4",
                "sensor_source": "polar_h10_chest_strap",
                "telemetry_parquet_ref": "telemetry/pratique/heart_rate_20260916.parquet"
            },
            "14-tactician": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "tactician",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "sport_type": "sailing",
                "split_metrics": {"tack_count": 8, "vmg_knots": 6.4},
                "monte_carlo_preset": "wind_shift_gust_envelope_10k"
            },
            "15-drydock": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "drydock",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "property_urn": "urn:drydock:property:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "deed_ref": "DEED-COUNTY-2024-998",
                "utility_metric_keys": ["water_liters", "grid_power_kwh"]
            },
            "16-squadron": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "squadron",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "vin": "1HGCR2F83HA000000",
                "engine_hours": 142.8,
                "telemetry_parquet_ref": "telemetry/squadron/obd_runs.parquet"
            },
            "17-supercargo": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "supercargo",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "serial_number": "SN-DELL-987654321",
                "mac_address": "00:1B:44:11:3A:B7",
                "warranty_expiry": "2028-12-31"
            },
            "18-commonplace": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "commonplace",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "isbn13": "9780441172719",
                "creator": "Frank Herbert",
                "shelf_state": "reading",
                "rating": 5
            },
            "19-chantey": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "chantey",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "enclosure_url": "https://media.example.org/podcasts/episode-42.mp3",
                "duration_seconds": 3720.5,
                "transcript_cas": "urn:chantey:transcript:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
            },
            "20-marquee": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "marquee",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "timecode_in": "01:04:22:15",
                "timecode_out": "01:06:10:00",
                "rush_bin": "reel_04_b_roll"
            },
            "21-scrimshaw": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "scrimshaw",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "cad_model_cas": "urn:scrimshaw:cad:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "gcode_profile": "prusa_mk4_petg_0.2mm",
                "toolpath_version": "v2.1.0"
            },
            "22-traverse": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "traverse",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "geojson_feature": {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.4194, 37.7749]
                    },
                    "properties": {"name": "San Francisco Harbor"}
                },
                "epsg_srid": 4326,
                "survey_datum": "WGS84"
            },
            "23-docent": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "docent",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "doi": "10.1145/3318464.3389700",
                "bibtex_key": "shannon1948mathematical",
                "arxiv_id": "2301.07041"
            },
            "24-proctor": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "proctor",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "docket_number": "1:24-cv-01234",
                "pacer_case_id": "nysd-584932",
                "statute_refs": ["17 U.S.C. § 107", "35 U.S.C. § 101"]
            },
            "25-ropewalk": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "ropewalk",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "repo_slug": "dotfiles/workstation",
                "remote_origin": "git@github.com:user/dotfiles.git",
                "dotfile_target_path": "~/.config/nvim"
            },
            "26-gavel": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "gavel",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T18:00:00Z"
                },
                "committee_slug": "finance-committee",
                "meeting_date": "2026-09-16",
                "bylaws_uri": "https://example.org/bylaws",
                "motion_tallies": [{"title": "Adopt Budget", "ayes": 5, "nays": 0, "abstentions": 1, "passed": True}]
            },
            "27-lineage": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "lineage",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "individual_urn": "urn:lineage:person:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "pedigree_branch": "maternal",
                "vital_dates": {"birth": "1920-04-15"},
                "gedcom_id": "@I0001@"
            },
            "28-legacy": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "legacy",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "trust_ref": "TRUST-2024-REVOCABLE",
                "living_will_cas": "urn:legacy:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "executor_contact_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba44",
                "durable_poa_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            },
            "29-arbor": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "arbor",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "taxonomic_species": "Quercus alba",
                "seed_vintage_year": 2023,
                "planting_zone": "7b",
                "soil_ph_optimal": 6.5
            },
            "30-the-glass": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "the-glass",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "station_id": "NOAA-SF-BAYSIDE",
                "barometric_hpa": 1013.25,
                "tide_gauge_urn": "urn:glass:tide:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "telemetry_parquet_ref": "telemetry/glass/baro_20260916.parquet"
            },
            "31-dispatch": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "dispatch",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "sender_urn": "urn:dispatch:station:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "recipient_urn": "urn:dispatch:station:018f62f8-9a3b-7d23-bf72-5b9c03bfba44",
                "postmark_date": "2026-09-16",
                "courier_tracking": "TRACK-1Z999999999"
            },
            "32-registry": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "registry",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "document_type": "passport",
                "issuing_jurisdiction": "US",
                "expiry_date": "2034-05-20",
                "encrypted_credential_cas": "urn:registry:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
            },
            "33-purser": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "purser",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "billing_cadence": "monthly",
                "vendor_urn": "urn:purser:vendor:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "monthly_spend_usd": 120.0,
                "cancellation_sla": "30 days"
            },
            "34-cadence": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "cadence",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "streak_count_current": 42,
                "target_frequency": "daily",
                "ritual_window": "morning",
                "best_streak": 100
            },
            "35-reckoning": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "reckoning",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "decision_framework": "SPADE",
                "pre_mortem_risk_tags": ["vendor_lock_in", "latency_spike"],
                "bias_audit_flags": ["sunk_cost_fallacy"]
            },
            "36-strongbox": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "strongbox",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "key_algorithm": "Ed25519",
                "public_key_fingerprint": "SHA256:7f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3c",
                "hardware_token_serial": "YUBI-12345678",
                "derivation_path": "m/44'/60'/0'/0/0"
            },
            "37-trajectory": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "trajectory",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "role_title": "Principal Architect",
                "organization_urn": "urn:trajectory:org:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "tenure_start": "2022-01-10",
                "case_study_slugs": ["global-sync-engine"]
            },
            "38-binnacle": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "binnacle",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "theological_tradition": "Stoicism",
                "credo_axiom_key": "amor_fati",
                "canonical_scripture_refs": ["Meditations IV.3"]
            },
            "39-claim": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "claim",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "patent_number": "US11842099B2",
                "jurisdiction_office": "USPTO",
                "filing_date": "2023-03-15",
                "prior_art_urns": ["urn:claim:patent:US10452390B1"]
            },
            "40-tribute": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "tribute",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "recipient_contact_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "sizing_chart_profile": {"shoe_eu": 43, "shirt": "L"},
                "reciprocity_balance": 1.5
            },
            "41-weft": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "weft",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "garment_category": "outerwear",
                "textile_composition": {"wool": 80, "cashmere": 20},
                "care_wash_spec": "Dry clean only",
                "tailoring_measurements": {"chest_cm": 104, "sleeve_cm": 65}
            },
            "42-reverie": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "reverie",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "dream_motif_tags": ["labyrinth", "ocean_voyage"],
                "lucidity_level": 3,
                "sleep_stage_anchor": "REM"
            },
            "43-provenance": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "provenance",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "appraisal_usd": 25000.0,
                "chain_of_custody_urns": ["urn:provenance:custodian:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"],
                "edition_number": "2/25",
                "authenticity_cert_cas": "urn:provenance:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba44"
            },
            "44-menagerie": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "menagerie",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "species_breed": "Canis lupus familiaris / Border Collie",
                "microchip_hex_id": "985141001234567",
                "vet_clinic_urn": "urn:menagerie:clinic:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "vaccination_schedule": [{"vaccine": "Rabies", "due_date": "2027-05-12"}]
            },
            "45-muster": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "muster",
                    "created_at": "2026-09-16",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "rally_point_coordinates": [-122.4194, 37.7749],
                "bug_out_tier": "72h",
                "ration_expiry_date": "2028-09-01",
                "comms_frequency_mhz": 146.520
            },
            "46-breadboard": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "breadboard",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "schematic_cas": "urn:breadboard:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "pcb_revision": "Rev C",
                "gpio_pinout_map": {"GPIO21": "SDA", "GPIO22": "SCL"},
                "operating_voltage_vdc": 3.3
            },
            "47-pavilion": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "pavilion",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "run_of_show_steps": [{"cue_time": "18:00", "activity": "Welcome Reception"}],
                "venue_reservation_urn": "urn:pavilion:venue:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "headcount_target": 150
            },
            "48-charthouse": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "charthouse",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "campaign_lore_node": "lore.third_age.fall_of_gondolin",
                "timeline_epoch": "Third Age",
                "scene_binder_ref": "act_1_scene_3"
            },
            "49-commonwealth": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "commonwealth",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "initiative_name": "Community Food Pantry",
                "hours_logged": 24.5,
                "volunteer_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "mutual_aid_batch_id": "batch_2026_09_A"
            },
            "50-relay": {
                "$pkm": {
                    "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "realm": "relay",
                    "created_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:00:00Z"
                },
                "dead_man_interval_days": 30,
                "heartbeat_received_at": "2026-09-16T12:00:00Z",
                "master_recovery_key_cas": "urn:relay:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
            },
        }

        for prefix, sample in samples.items():
            with self.subTest(sample_realm=prefix):
                schema_path = _SCHEMAS_DIR / "v1" / "realms" / f"{prefix}.schema.json"
                schema_obj = self._load_json(schema_path)
                validator = Draft202012Validator(schema_obj, registry=registry)
                validator.validate(sample)



if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSchemaFiles)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
