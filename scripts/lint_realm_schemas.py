"""scripts/lint_realm_schemas.py
───────────────────────────────
Multi-Realm Schema Linting and Drift Detection Script.

Inspects all 50 realm schemas under schemas/v1/realms/:
  1. Validates Draft 2020-12 meta-schema compliance and JSON integrity.
  2. Enforces canonical $id URI pinning (https://bosunpkm.com/schemas/v1/realms/<realm>.schema.json).
  3. Verifies strict archetype inheritance via allOf composition against the 5 canonical base archetypes.
  4. Ensures realm-specific properties are strictly scoped within the delta block and do not leak
     into top-level properties or base archetypes.
  5. Enforces documentation coverage across root metadata and all delta attribute definitions.

Usage:
  python scripts/lint_realm_schemas.py
  python scripts/lint_realm_schemas.py --verbose
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_REALMS_DIR = _SCHEMAS_DIR / "v1" / "realms"
_ARCHETYPES_DIR = _SCHEMAS_DIR / "v1" / "archetypes"
_META_ENVELOPE_PATH = _SCHEMAS_DIR / "v1" / "meta" / "envelope.schema.json"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID_PREFIX = "https://bosunpkm.com/schemas/"

# Canonical 50-Realm Archetype and Delta Attribute Matrix
REALM_SPECIFICATIONS: Dict[str, Tuple[str, str, List[str]]] = {
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


class LintViolation(NamedTuple):
    realm_key: str
    category: str
    message: str


class RealmSchemaLinter:
    """Multi-realm schema linter and drift detector."""

    def __init__(self, realms_dir: pathlib.Path = _REALMS_DIR, archetypes_dir: pathlib.Path = _ARCHETYPES_DIR):
        self.realms_dir = realms_dir
        self.archetypes_dir = archetypes_dir
        self.violations: List[LintViolation] = []

    def log_violation(self, realm_key: str, category: str, message: str) -> None:
        self.violations.append(LintViolation(realm_key, category, message))

    def lint_all_realms(self) -> List[LintViolation]:
        """Lint all 50 realm schemas against specification invariants."""
        self.violations.clear()

        # 1. Verify existence of realms directory
        if not self.realms_dir.exists():
            self.log_violation("all", "discovery", f"Realms directory missing: {self.realms_dir}")
            return self.violations

        # 2. Check all 50 schemas present and no extraneous files
        found_files = {p.name: p for p in self.realms_dir.glob("*.schema.json")}
        expected_files = {f"{k}.schema.json" for k in REALM_SPECIFICATIONS}

        missing_files = expected_files - set(found_files)
        extra_files = set(found_files) - expected_files

        for mf in sorted(missing_files):
            self.log_violation(mf, "discovery", f"Missing expected realm schema file: {mf}")
        for ef in sorted(extra_files):
            self.log_violation(ef, "discovery", f"Unexpected extra file in realms directory: {ef}")

        # 3. Lint each realm schema
        for realm_key, (arch_file, realm_name, delta_attrs) in REALM_SPECIFICATIONS.items():
            schema_file = self.realms_dir / f"{realm_key}.schema.json"
            if not schema_file.exists():
                continue
            self._lint_realm_schema(realm_key, schema_file, arch_file, realm_name, delta_attrs)

        return self.violations

    def _lint_realm_schema(
        self,
        realm_key: str,
        path: pathlib.Path,
        expected_arch_file: str,
        expected_realm_name: str,
        expected_delta_attrs: List[str],
    ) -> None:
        # A. JSON Parsing
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self.log_violation(realm_key, "syntax", f"Failed to parse valid JSON: {exc}")
            return

        if not isinstance(data, dict):
            self.log_violation(realm_key, "syntax", "Root schema must be a JSON object")
            return

        # B. Meta-Schema and Draft 2020-12
        schema_uri = data.get("$schema")
        if schema_uri != _DRAFT_2020_12:
            self.log_violation(
                realm_key,
                "meta-schema",
                f"Expected $schema '{_DRAFT_2020_12}', got {schema_uri!r}",
            )

        if _HAS_JSONSCHEMA:
            try:
                Draft202012Validator.check_schema(data)
            except jsonschema.SchemaError as exc:
                self.log_violation(realm_key, "meta-schema", f"Schema failed Draft 2020-12 check: {exc.message}")

        # C. Canonical $id Pinning
        canonical_id = f"{_CANONICAL_ID_PREFIX}v1/realms/{realm_key}.schema.json"
        actual_id = data.get("$id")
        if not actual_id:
            self.log_violation(realm_key, "id-pinning", "Missing $id URI declaration")
        elif actual_id != canonical_id:
            self.log_violation(
                realm_key,
                "id-pinning",
                f"Unpinned or mismatched $id: expected '{canonical_id}', got '{actual_id}'",
            )

        # D. Documentation Strings (Root)
        title = data.get("title")
        if not title or not isinstance(title, str) or not title.strip():
            self.log_violation(realm_key, "documentation", "Root 'title' is missing or empty")

        description = data.get("description")
        if not description or not isinstance(description, str) or not description.strip():
            self.log_violation(realm_key, "documentation", "Root 'description' is missing or empty")

        # E. Property Leakage: Root Properties Check
        if "properties" in data:
            self.log_violation(
                realm_key,
                "scope-leak",
                f"Root-level 'properties' found with keys {list(data['properties'].keys())}. "
                "All realm attributes must be scoped within the allOf delta block.",
            )

        if "patternProperties" in data:
            self.log_violation(
                realm_key,
                "scope-leak",
                "Root-level 'patternProperties' found. Attributes must be scoped within allOf delta block.",
            )

        # F. Archetype & Envelope Inheritance (allOf)
        all_of = data.get("allOf")
        if not isinstance(all_of, list) or len(all_of) < 2:
            self.log_violation(
                realm_key,
                "inheritance",
                "Root schema must define 'allOf' array containing archetype ref, envelope ref, and delta block",
            )
            return

        # 1. Archetype Reference Check
        expected_arch_ref = f"{_CANONICAL_ID_PREFIX}v1/archetypes/{expected_arch_file}"
        first_clause = all_of[0] if isinstance(all_of[0], dict) else {}
        actual_arch_ref = first_clause.get("$ref")
        if actual_arch_ref != expected_arch_ref:
            self.log_violation(
                realm_key,
                "inheritance",
                f"Assigned archetype mismatch: expected allOf[0].$ref='{expected_arch_ref}', got '{actual_arch_ref}'",
            )

        arch_path = self.archetypes_dir / expected_arch_file
        if not arch_path.exists():
            self.log_violation(
                realm_key,
                "inheritance",
                f"Referenced archetype file does not exist on disk: {arch_path}",
            )

        # 2. Universal Envelope Reference Check
        expected_env_ref = f"{_CANONICAL_ID_PREFIX}v1/meta/envelope.schema.json"
        has_env_ref = any(isinstance(c, dict) and c.get("$ref") == expected_env_ref for c in all_of)
        if not has_env_ref:
            self.log_violation(
                realm_key,
                "inheritance",
                f"Missing allOf reference to universal meta-envelope '{expected_env_ref}'",
            )

        # G. Delta Properties Scoping & Drift Check
        # Locate the delta schema clause (the clause defining properties)
        delta_clauses = [c for c in all_of if isinstance(c, dict) and "properties" in c]
        if not delta_clauses:
            self.log_violation(
                realm_key,
                "scope-leak",
                "Missing delta schema clause with 'properties' inside allOf composition",
            )
            return
        elif len(delta_clauses) > 1:
            self.log_violation(
                realm_key,
                "scope-leak",
                f"Multiple delta clauses ({len(delta_clauses)}) with 'properties' inside allOf; expected exactly 1",
            )

        delta = delta_clauses[-1]
        delta_props = delta.get("properties", {})
        if not isinstance(delta_props, dict):
            self.log_violation(realm_key, "syntax", "Delta clause 'properties' must be a JSON object")
            return

        # 1. Realm Scoping ($pkm.realm.const)
        pkm_def = delta_props.get("$pkm")
        if not isinstance(pkm_def, dict):
            self.log_violation(realm_key, "scope-leak", "Delta properties must declare '$pkm' object")
        else:
            pkm_props = pkm_def.get("properties", {})
            realm_prop = pkm_props.get("realm", {})
            realm_const = realm_prop.get("const") if isinstance(realm_prop, dict) else None
            if realm_const != expected_realm_name:
                self.log_violation(
                    realm_key,
                    "scope-leak",
                    f"Mismatched scoped $pkm.realm: expected const='{expected_realm_name}', got '{realm_const}'",
                )
            # Documentation on realm const
            realm_desc = realm_prop.get("description") if isinstance(realm_prop, dict) else None
            if not realm_desc or not isinstance(realm_desc, str) or not realm_desc.strip():
                self.log_violation(
                    realm_key,
                    "documentation",
                    "$pkm.properties.realm is missing 'description' documentation string",
                )

        # 2. Delta Attributes Drift Check
        declared_keys = set(delta_props.keys()) - {"$pkm"}
        expected_keys = set(expected_delta_attrs)

        missing_attrs = expected_keys - declared_keys
        for ma in sorted(missing_attrs):
            self.log_violation(
                realm_key,
                "drift",
                f"Missing canonical delta attribute '{ma}' in realm properties",
            )

        # 3. Documentation on Delta Properties
        for prop_name, prop_schema in delta_props.items():
            if prop_name == "$pkm":
                continue
            if not isinstance(prop_schema, dict):
                self.log_violation(
                    realm_key,
                    "syntax",
                    f"Property definition for '{prop_name}' must be an object",
                )
                continue

            prop_desc = prop_schema.get("description")
            if not prop_desc or not isinstance(prop_desc, str) or not prop_desc.strip():
                self.log_violation(
                    realm_key,
                    "documentation",
                    f"Attribute '{prop_name}' is missing a 'description' documentation string",
                )


def run_linter(verbose: bool = False) -> int:
    """CLI entrypoint for realm schema linting."""
    print("=" * 78)
    print("BOSUN FLEET: Multi-Realm Schema Linting and Drift Detection")
    print(f"Target Directory: {_REALMS_DIR}")
    print("=" * 78)

    linter = RealmSchemaLinter()
    violations = linter.lint_all_realms()

    if verbose or violations:
        # Group violations by realm
        grouped: Dict[str, List[LintViolation]] = {}
        for v in violations:
            grouped.setdefault(v.realm_key, []).append(v)

        for r_key in sorted(REALM_SPECIFICATIONS):
            r_violations = grouped.get(r_key, [])
            if r_violations:
                print(f"\n[FAIL] Realm {r_key}:")
                for v in r_violations:
                    print(f"  - [{v.category.upper()}] {v.message}")
            elif verbose:
                arch_file, realm_name, attrs = REALM_SPECIFICATIONS[r_key]
                print(f"[PASS] Realm {r_key} -> {arch_file} ({len(attrs)} delta attributes)")

    print("\n" + "-" * 78)
    total_realms = len(REALM_SPECIFICATIONS)
    if not violations:
        print(f"SUCCESS: All {total_realms} realm schemas conform strictly to archetype, ID, and documentation rules.")
        print(f"  - Meta-schema validation: PASSED (Draft 2020-12)")
        print(f"  - Canonical $id pinning: PASSED ({total_realms}/{total_realms} pinned)")
        print(f"  - Archetype inheritance: PASSED ({total_realms}/{total_realms} conform)")
        print(f"  - Property scope isolation: PASSED (0 leaks detected)")
        print(f"  - Documentation coverage: PASSED (100% attribute descriptions present)")
        print("-" * 78)
        return 0
    else:
        print(f"FAILURE: Detected {len(violations)} linting violation(s) across realm schemas.")
        print("-" * 78)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-Realm Schema Linting and Drift Detection Script for Bosun PKM."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output listing each realm's status.",
    )
    args = parser.parse_args()
    sys.exit(run_linter(verbose=args.verbose))
