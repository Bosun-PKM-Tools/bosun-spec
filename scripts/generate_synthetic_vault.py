"""scripts/generate_synthetic_vault.py
───────────────────────────────────
Generates a 50-realm synthetic demo vault under fixtures/synthetic_vault/.
Creates 4 populated, schema-compliant, interconnected markdown notes per realm
(200 total notes) with zero broken URNs across the life repository.

Cross-realm relationship wiring highlights:
  - Trice task -> Yeoman contact (assignedToContact)
  - Supercargo gear -> Quartermaster tx (purchasedViaTx)
  - Careen project -> Trice task (actionItemDerivedFrom)
  - Pratique vitals -> Yeoman provider (consultedProvider)
  - Logbook entries -> attendedEvent
  - Drydock property -> purchasedViaTx
  - Legacy trust -> executor_contact_urn
  - Dispatch courier -> sender_urn / recipient_urn
  - Commonwealth aid -> volunteer_urn
  - Pavilion event -> venue_reservation_urn / attendedEvent
  - Relay deadman -> master_recovery_key_cas / assignedToContact

Usage:
  python scripts/generate_synthetic_vault.py
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys
import time
import uuid
from typing import Any, Dict, List, Tuple

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_VAULT_DIR = _REPO_ROOT / "fixtures" / "synthetic_vault"

_ARCHETYPE_FILES = (
    "v1/archetypes/catalog-dossier.schema.json",
    "v1/archetypes/interaction-ledger.schema.json",
    "v1/archetypes/dual-track-telemetry.schema.json",
    "v1/archetypes/stage-gate-manifest.schema.json",
    "v1/archetypes/sovereign-vault.schema.json",
)


def generate_uuidv7(seed_key: str | None = None) -> str:
    """Generate an RFC 9562-compliant UUIDv7 string."""
    ts_ms = 1789639200000  # 2026-09-17T10:00:00Z fixed timestamp
    if seed_key is not None:
        h = hashlib.sha256(seed_key.encode("utf-8")).digest()
        rand_a = int.from_bytes(h[0:2], "big") & 0x0FFF
        rand_b = int.from_bytes(h[2:10], "big") & 0x3FFFFFFFFFFFFFFF
    else:
        rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
        rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
    uuid_int = (ts_ms << 80) | (7 << 76) | (rand_a << 64) | (2 << 62) | rand_b
    return str(uuid.UUID(int=uuid_int))


def build_schema_registry() -> Tuple[Registry, Dict[str, Draft202012Validator]]:
    """Load referencing Registry with base archetypes and compile realm validators."""
    reg = Registry()
    for rel in _ARCHETYPE_FILES:
        path = _SCHEMAS_DIR / rel
        obj = json.loads(path.read_text(encoding="utf-8"))
        reg = reg.with_resource(obj["$id"], Resource.from_contents(obj))

    env_path = _SCHEMAS_DIR / "v1" / "meta" / "envelope.schema.json"
    env_obj = json.loads(env_path.read_text(encoding="utf-8"))
    reg = reg.with_resource(env_obj["$id"], Resource.from_contents(env_obj))

    validators: Dict[str, Draft202012Validator] = {}
    for p in (_SCHEMAS_DIR / "v1" / "realms").glob("*.schema.json"):
        realm_key = p.name.replace(".schema.json", "")
        schema_obj = json.loads(p.read_text(encoding="utf-8"))
        validators[realm_key] = Draft202012Validator(schema_obj, registry=reg)

    return reg, validators


# Specification metadata for each of the 4 notes in all 50 realms
# Format: (slug, title, realm_attrs_fn, body_headings)
REALM_NOTE_DEFINITIONS: Dict[str, List[Tuple[str, str, Dict[str, Any], List[str]]]] = {
    "01-bosun": [
        (
            "offline-first-sovereign-graph",
            "Offline-First Sovereign Knowledge Graph Architecture",
            {"zettel_type": "concept", "wikilinks": ["[[Zettelkasten Topology]]", "[[Local-First Software]]"], "ast_version": "1.0.0"},
            ["## Conceptual Substrate", "## Sovereign Local Storage", "## Offline Graph Invariants"],
        ),
        (
            "content-addressed-storage-cas",
            "Content-Addressed Storage Substrate in Bosun",
            {"zettel_type": "structure", "wikilinks": ["[[Cryptographic Hashes]]", "[[CAS Manifests]]"], "ast_version": "1.0.0"},
            ["## CAS Architecture", "## SHA-256 Storage Paths", "## Immutability Invariants"],
        ),
        (
            "transclusion-syntax-and-ast",
            "Transclusion Syntax and Marlinspike AST Parsing",
            {"zettel_type": "reference", "wikilinks": ["[[Markdown Parser]]", "[[Block Embeds]]"], "ast_version": "1.0.0"},
            ["## Transclusion Grammars", "## Block Anchor Syntax", "## Resolution Pipelines"],
        ),
        (
            "topological-note-indexing",
            "Topological Indexing of Concept Clusters",
            {"zettel_type": "hub", "wikilinks": ["[[Concept Index]]", "[[Graph Traversal]]"], "ast_version": "1.0.0"},
            ["## Cluster Topology", "## Hub Node Traversal", "## Knowledge Synthesis"],
        ),
    ],
    "02-yeoman": [
        (
            "contact-ada-lovelace",
            "Ada Lovelace - Analytical Computing Pioneer",
            {"cadence_days": 14, "channels": [{"kind": "email", "value": "ada@analyticalengine.org", "label": "work"}], "last_contact_date": "2026-09-16"},
            ["## Contact Overview", "## Ongoing Collaborations", "## Channel Registry"],
        ),
        (
            "contact-charles-babbage",
            "Charles Babbage - Mechanical Engine Designer",
            {"cadence_days": 30, "channels": [{"kind": "email", "value": "babbage@difference.engine", "label": "office"}], "last_contact_date": "2026-09-10"},
            ["## Mechanical Design Discussions", "## Scheduled Reviews", "## Correspondence Notes"],
        ),
        (
            "contact-grace-hopper",
            "Grace Hopper - Compiler Systems Architect",
            {"cadence_days": 7, "channels": [{"kind": "email", "value": "hopper@navy.mil", "label": "work"}], "last_contact_date": "2026-09-17"},
            ["## Compiler Working Group", "## Syntax Standardization", "## Bi-Weekly Check-in"],
        ),
        (
            "contact-dr-elena-vance",
            "Dr. Elena Vance - Primary Healthcare Provider",
            {"cadence_days": 90, "channels": [{"kind": "phone", "value": "+1-555-0199", "label": "clinic"}], "last_contact_date": "2026-09-01"},
            ["## Clinical Practice", "## Care Consultations", "## Direct Line & Hours"],
        ),
    ],
    "03-trice": [
        (
            "task-archive-ingest",
            "Execute Bi-Weekly Historical Archive Ingest",
            {"task_state": "active", "priority": "p1", "recurrence_rule": "RRULE:FREQ=WEEKLY;INTERVAL=2"},
            ["## Task Scope", "## Ingest Steps", "## Verification Criteria"],
        ),
        (
            "task-quarterly-tax-prep",
            "Reconcile Hardware Purchases for Quarterly Ledger",
            {"task_state": "pending", "priority": "p2", "recurrence_rule": "RRULE:FREQ=MONTHLY;BYMONTH=3,6,9,12"},
            ["## Reconciliation Objectives", "## Receipts Checklist", "## Ledger Export"],
        ),
        (
            "task-campaign-worldbuilding",
            "Compile Charthouse Campaign Lore Canon",
            {"task_state": "active", "priority": "p3", "recurrence_rule": ""},
            ["## Campaign Milestones", "## Narrative Outlines", "## Character Dossiers"],
        ),
        (
            "task-cardiac-vitals-review",
            "Review Resting Heart Rate and Telemetry Anomalies",
            {"task_state": "done", "priority": "p2", "recurrence_rule": "RRULE:FREQ=WEEKLY"},
            ["## Clinical Review Goals", "## Observation Log", "## Follow-up Directives"],
        ),
    ],
    "04-logbook": [
        (
            "journal-2026-09-16",
            "Daily Logbook Journal - 2026-09-16",
            {"journal_date": "2026-09-16", "agenda_blocks": [{"title": "Morning Standup", "start": "2026-09-16T08:00:00Z"}, {"title": "Engineering Review", "start": "2026-09-16T14:00:00Z"}], "transclusion_anchors": ["standup-notes", "evening-review"]},
            ["## Morning Reflections", "## Execution Agenda", "## Evening Debrief"],
        ),
        (
            "journal-2026-09-17",
            "Daily Logbook Journal - 2026-09-17",
            {"journal_date": "2026-09-17", "agenda_blocks": [{"title": "Architecture Sync", "start": "2026-09-17T09:00:00Z"}, {"title": "Deep Work", "start": "2026-09-17T13:00:00Z"}], "transclusion_anchors": ["sync-notes", "daily-wins"]},
            ["## Chronological Log", "## Deep Work Session", "## Daily Retrospective"],
        ),
        (
            "event-quarterly-symposium",
            "Annual Systems Engineering Symposium",
            {"journal_date": "2026-09-15", "agenda_blocks": [{"title": "Keynote Address", "start": "2026-09-15T10:00:00Z"}, {"title": "Panel Discussion", "start": "2026-09-15T15:00:00Z"}], "transclusion_anchors": ["keynote-summary"]},
            ["## Event Scope", "## Speaker Roster", "## Key Takeaways"],
        ),
        (
            "event-community-town-hall",
            "Community Mutual Aid Assembly",
            {"journal_date": "2026-09-14", "agenda_blocks": [{"title": "Welcome", "start": "2026-09-14T18:00:00Z"}, {"title": "Breakout Discussions", "start": "2026-09-14T19:00:00Z"}], "transclusion_anchors": ["action-items"]},
            ["## Agenda Outline", "## Community Proposals", "## Next Steps"],
        ),
    ],
    "05-quartermaster": [
        (
            "tx-server-rack-purchase",
            "Quartermaster Ledger: Dell Workstation Node Procurement",
            {"beancount_account": "Expenses:Equipment:Hardware", "tx_hash": "e8391b4029f8c12a3d", "currency_code": "USD"},
            ["## Transaction Postings", "## Invoice Metadata", "## Asset Capitalization"],
        ),
        (
            "tx-consulting-retainer-disbursement",
            "Quartermaster Ledger: Systems Architecture Advisory Fee",
            {"beancount_account": "Income:Consulting:Advisory", "tx_hash": "f9420c813a47b19e4c", "currency_code": "USD"},
            ["## Retainer Reconciliation", "## Client Allocation", "## Bank Posting"],
        ),
        (
            "tx-cloud-storage-subscription",
            "Quartermaster Ledger: Content-Addressable Storage Tier",
            {"beancount_account": "Expenses:Software:Subscriptions", "tx_hash": "a1239c847b28f9103e", "currency_code": "USD"},
            ["## Monthly Allocation", "## Service Invoicing", "## Balance Reconciliation"],
        ),
        (
            "tx-slipway-winch-lubricant",
            "Quartermaster Ledger: Marine Slipway Maintenance Materials",
            {"beancount_account": "Expenses:Maintenance:Drydock", "tx_hash": "b88231f409ac72d19f", "currency_code": "USD"},
            ["## Procurement Posting", "## Facility Maintenance Ref", "## Ledger Audit"],
        ),
    ],
    "06-harbor": [
        (
            "route-home-portal",
            "Harbor Ingress: Sovereign Fleet Portal Landing",
            {"slug": "fleet-portal", "edge_route": "/", "render_template": "landing-page"},
            ["## Ingress Route Configuration", "## Template Specification", "## Cache Policies"],
        ),
        (
            "route-documentation-hub",
            "Harbor Ingress: Technical Documentation Tree",
            {"slug": "docs-architecture", "edge_route": "/docs/architecture", "render_template": "docs-layout"},
            ["## Documentation Structure", "## Sidebar Navigation", "## Edge Purge Rules"],
        ),
        (
            "route-knowledge-feed",
            "Harbor Ingress: Public Zettelkasten Feed",
            {"slug": "public-notes", "edge_route": "/feed/notes", "render_template": "atom-feed"},
            ["## Feed Parameters", "## Syndication Invariants", "## Content Filtering"],
        ),
        (
            "route-status-dashboard",
            "Harbor Ingress: Fleet Operational Health Telemetry",
            {"slug": "status-live", "edge_route": "/status", "render_template": "telemetry-view"},
            ["## Live Health Indicators", "## Data Pipeline", "## Real-time Metrics"],
        ),
    ],
    "07-press": [
        (
            "press-spec-poster-architecture",
            "Press Cut Sheet: Bosun Topology Poster (A2)",
            {"sku": "PRESS-POSTER-001", "vector_asset_cas": "urn:press:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "cut_sheet_spec": {"width_mm": 420.0, "height_mm": 594.0}},
            ["## Dimensions & Substrate", "## Vector Linework", "## Pre-press Checklist"],
        ),
        (
            "press-spec-field-journal",
            "Press Cut Sheet: Sovereign Pocket Logbook (B6)",
            {"sku": "PRESS-BOOK-002", "vector_asset_cas": "urn:press:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "cut_sheet_spec": {"width_mm": 125.0, "height_mm": 176.0}},
            ["## Binding Specifications", "## Signature Folding", "## Cover Stock"],
        ),
        (
            "press-spec-schematic-blueprint",
            "Press Cut Sheet: Hardware Architecture Blueprint (A1)",
            {"sku": "PRESS-SHEET-003", "vector_asset_cas": "urn:press:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "cut_sheet_spec": {"width_mm": 594.0, "height_mm": 841.0}},
            ["## Draughting Standards", "## Plotter Profiles", "## Archival Inks"],
        ),
        (
            "press-spec-reference-cards",
            "Press Cut Sheet: GTD Action Matrix Index Cards",
            {"sku": "PRESS-CARD-004", "vector_asset_cas": "urn:press:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "cut_sheet_spec": {"width_mm": 74.0, "height_mm": 105.0}},
            ["## Die Cutting Rules", "## Cardstock Weight", "## Finishing Varnishes"],
        ),
    ],
    "08-embers": [
        (
            "media-photo-slipway-refit",
            "Embers Asset: Drydock Slipway Structural Photo",
            {"exif_payload": {"iso": 100, "focal_length": "35mm"}, "media_hash_sha256": "39910d9446d3289a84a6015690ff39947aa579bb88ef2cc0d463e261d76378e9", "codec": "image/jpeg"},
            ["## Asset Overview", "## Optical Metadata", "## Subject Identification"],
        ),
        (
            "media-photo-server-cluster",
            "Embers Asset: Primary Compute Enclosure Hardware",
            {"exif_payload": {"iso": 400, "focal_length": "50mm"}, "media_hash_sha256": "7c222fb2927d828af22f592134e8932480637c0d508875424564c483a936a541", "codec": "image/jpeg"},
            ["## Rack Configuration", "## Physical Cable Runs", "## Inspection Timestamps"],
        ),
        (
            "media-photo-botanical-seedling",
            "Embers Asset: Heritage Oak Seedling Shoot",
            {"exif_payload": {"iso": 200, "focal_length": "90mm"}, "media_hash_sha256": "4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865", "codec": "image/jpeg"},
            ["## Botanical Morphology", "## Germination Environment", "## Growth Records"],
        ),
        (
            "media-photo-cad-prototype",
            "Embers Asset: 3D Printed Gimbal Bracket Prototype",
            {"exif_payload": {"iso": 160, "focal_length": "28mm"}, "media_hash_sha256": "53c234e5e8472b6ac51c1ae1cab3fe06fad053beb8ebfd8977b010655bfdd3c3", "codec": "image/jpeg"},
            ["## Layer Line Quality", "## Mechanical Tolerances", "## Defect Assessment"],
        ),
    ],
    "09-careen": [
        (
            "project-worldbuilding-refit",
            "Careen Project: Narrative Campaign Canon Refactor",
            {"kanban_stage": "in_progress", "sprint_ref": "sprint-2026-38", "milestone_urn": "urn:careen:milestone:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"},
            ["## Project Scope", "## Stage-Gate Deliverables", "## Sprint Backlog"],
        ),
        (
            "project-vault-scaffolding",
            "Careen Project: 50-Realm Fleet Vault Modernization",
            {"kanban_stage": "in_review", "sprint_ref": "sprint-2026-37", "milestone_urn": "urn:careen:milestone:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"},
            ["## Refactor Goals", "## Automated Testing Gates", "## Deployment Verification"],
        ),
        (
            "project-slipway-overhaul",
            "Careen Project: Marine Drydock Slipway Winch Automation",
            {"kanban_stage": "ready", "sprint_ref": "sprint-2026-39", "milestone_urn": "urn:careen:milestone:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"},
            ["## Engineering Feasibility", "## Electrical Schematics", "## Mechanical Assembly"],
        ),
        (
            "project-mobile-telemetry",
            "Careen Project: Real-time Biometric Ingest Engine",
            {"kanban_stage": "done", "sprint_ref": "sprint-2026-36", "milestone_urn": "urn:careen:milestone:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"},
            ["## Implementation Review", "## Parquet Storage Performance", "## Retrospective"],
        ),
    ],
    "10-primer": [
        (
            "flashcard-dijkstra-shortest-path",
            "Primer Card: Dijkstra Algorithm State Invariants",
            {"spaced_interval_days": 7.0, "ease_factor": 2.6, "skill_node": "comp_sci.graph_theory"},
            ["## Core Principles", "## Active Recall Prompts", "## Edge Relaxations"],
        ),
        (
            "flashcard-raft-consensus",
            "Primer Card: Raft Consensus Election Safety",
            {"spaced_interval_days": 14.0, "ease_factor": 2.4, "skill_node": "distributed_systems.consensus"},
            ["## Consensus Invariants", "## Split Vote Scenarios", "## Log Replication"],
        ),
        (
            "flashcard-beancount-double-entry",
            "Primer Card: Double-Entry Conservation Rules",
            {"spaced_interval_days": 21.0, "ease_factor": 2.8, "skill_node": "finance.accounting"},
            ["## Conservation Law", "## Zero Sum Postings", "## Multi-Currency Balances"],
        ),
        (
            "flashcard-cellular-respiration",
            "Primer Card: Mitochondrial ATP Synthesis Pathways",
            {"spaced_interval_days": 3.0, "ease_factor": 2.2, "skill_node": "biology.biochemistry"},
            ["## Metabolic Cycles", "## Electron Transport Chain", "## Proton Gradients"],
        ),
    ],
    "11-passage": [
        (
            "itinerary-edinburgh-express",
            "Passage Itinerary: London Kings Cross to Edinburgh Waverley",
            {"transit_mode": "rail", "booking_ref": "LNER-98421-E", "waypoints": [{"name": "London Kings Cross"}, {"name": "York"}, {"name": "Newcastle"}, {"name": "Edinburgh Waverley"}]},
            ["## Route Overview", "## Timetable & Connections", "## Waypoints Log"],
        ),
        (
            "itinerary-transatlantic-voyage",
            "Passage Itinerary: Southampton to New York Harbor",
            {"transit_mode": "sea", "booking_ref": "CUNARD-7712-W", "waypoints": [{"name": "Southampton"}, {"name": "Cobh"}, {"name": "New York Pier 88"}]},
            ["## Nautical Waypoints", "## Passage Watches", "## Harbor Moorings"],
        ),
        (
            "itinerary-highland-walking-trail",
            "Passage Itinerary: West Highland Way Backpacking Track",
            {"transit_mode": "foot", "booking_ref": "WHW-TREK-04", "waypoints": [{"name": "Milngavie"}, {"name": "Drymen"}, {"name": "Rowardennan"}, {"name": "Fort William"}]},
            ["## Trail Elevations", "## Campsite Coordinates", "## Gear Check"],
        ),
        (
            "itinerary-continental-air-hop",
            "Passage Itinerary: Zurich Airport to London Heathrow",
            {"transit_mode": "air", "booking_ref": "LX-318-ZUR", "waypoints": [{"name": "Zurich ZRH"}, {"name": "London LHR"}]},
            ["## Flight Manifest", "## Terminal Coordinates", "## Carbon Offsetting"],
        ),
    ],
    "12-galley": [
        (
            "recipe-sourdough-boule",
            "Galley Formula: 75% Hydration Artisan Sourdough",
            {"servings": 8.0, "prep_time_minutes": 1440, "ingredients_schema": [{"item": "Bread Flour", "amount": 500.0, "unit": "g"}, {"item": "Water", "amount": 375.0, "unit": "ml"}, {"item": "Sourdough Starter", "amount": 100.0, "unit": "g"}, {"item": "Sea Salt", "amount": 10.0, "unit": "g"}]},
            ["## Fermentation Schedule", "## Dough Formulation", "## Baking & Crumb Notes"],
        ),
        (
            "recipe-steel-cut-oats",
            "Galley Formula: Slow-Simmered Steel Cut Porridge",
            {"servings": 4.0, "prep_time_minutes": 35, "ingredients_schema": [{"item": "Steel Cut Oats", "amount": 150.0, "unit": "g"}, {"item": "Water", "amount": 600.0, "unit": "ml"}, {"item": "Cinnamon", "amount": 5.0, "unit": "g"}]},
            ["## Breakfast Preparation", "## Nutritional Ratios", "## Serving Suggestions"],
        ),
        (
            "recipe-hearty-lentil-stew",
            "Galley Formula: Mediterranean Brown Lentil Stew",
            {"servings": 6.0, "prep_time_minutes": 55, "ingredients_schema": [{"item": "Brown Lentils", "amount": 300.0, "unit": "g"}, {"item": "Carrots", "amount": 200.0, "unit": "g"}, {"item": "Celery", "amount": 150.0, "unit": "g"}, {"item": "Olive Oil", "amount": 30.0, "unit": "ml"}]},
            ["## Mirepoix Base", "## Simmering Instructions", "## Storage & Freezing"],
        ),
        (
            "recipe-roasted-vegetable-medley",
            "Galley Formula: Herb-Infused Roasted Root Vegetables",
            {"servings": 4.0, "prep_time_minutes": 40, "ingredients_schema": [{"item": "Parsnips", "amount": 250.0, "unit": "g"}, {"item": "Beets", "amount": 250.0, "unit": "g"}, {"item": "Rosemary", "amount": 10.0, "unit": "g"}]},
            ["## Roasting Temps", "## Seasoning Profile", "## Plating Notes"],
        ),
    ],
    "13-pratique": [
        (
            "vitals-cardiology-panel",
            "Pratique Record: Resting Heart Rate & HRV Profile",
            {"fhir_code": "8867-4", "sensor_source": "Polar H10 ECG Chest Strap", "telemetry_parquet_ref": "telemetry/pratique/cardiac_hrv.parquet"},
            ["## Biometric Telemetry", "## Autonomic Tone Indices", "## Clinical Evaluation"],
        ),
        (
            "vitals-respiratory-capacity",
            "Pratique Record: Forced Expiratory Volume (FEV1)",
            {"fhir_code": "19926-5", "sensor_source": "Spirometry Sensor Module", "telemetry_parquet_ref": "telemetry/pratique/pulmonary.parquet"},
            ["## Pulmonary Metrics", "## Flow-Volume Loops", "## Trend Analysis"],
        ),
        (
            "vitals-sleep-architecture",
            "Pratique Record: Polysomnographic Sleep Stages",
            {"fhir_code": "93832-4", "sensor_source": "EEG Headband Sensor", "telemetry_parquet_ref": "telemetry/pratique/sleep_stages.parquet"},
            ["## Sleep Efficiency", "## Deep Sleep Totals", "## Recovery Index"],
        ),
        (
            "vitals-blood-pressure-panel",
            "Pratique Record: Ambulatory Blood Pressure Telemetry",
            {"fhir_code": "85354-9", "sensor_source": "Omron Upper Arm Monitor", "telemetry_parquet_ref": "telemetry/pratique/abpm.parquet"},
            ["## Systolic / Diastolic Averages", "## Diurnal Variations", "## Provider Feedback"],
        ),
    ],
    "14-tactician": [
        (
            "simulation-solent-regatta",
            "Tactician Simulation: Solent Tidal Gate Windward Leg",
            {"sport_type": "sailing", "split_metrics": {"speed_target_knots": 6.8, "vmg_upwind": 5.4}, "monte_carlo_preset": "solent_tide_wind_shift"},
            ["## Race Course Geometry", "## Tidal Current Projections", "## Optimum Laylines"],
        ),
        (
            "simulation-marathon-pacing",
            "Tactician Simulation: Negative Split Marathon Pacing",
            {"sport_type": "running", "split_metrics": {"target_pace_per_km": 255.0, "cadence_spm": 182.0}, "monte_carlo_preset": "elevation_fatigue_model"},
            ["## Pacing Strategy", "## Metabolic Expenditure", "## Split Checkpoints"],
        ),
        (
            "simulation-cycling-time-trial",
            "Tactician Simulation: 40km Aerodynamic Power Profiling",
            {"sport_type": "cycling", "split_metrics": {"normalized_power_watts": 310.0, "cda_drag": 0.215}, "monte_carlo_preset": "wind_yaw_variability"},
            ["## Aerodynamic Resistance", "## Target Wattage Spans", "## Course Breakdown"],
        ),
        (
            "simulation-triathlon-transition",
            "Tactician Simulation: Transition Efficiency & Heart Rate Settling",
            {"sport_type": "triathlon", "split_metrics": {"t1_seconds": 90.0, "t2_seconds": 65.0}, "monte_carlo_preset": "cardiovascular_drift"},
            ["## Transition Protocol", "## Biomechanical Shifting", "## Recovery Intervals"],
        ),
    ],
    "15-drydock": [
        (
            "facility-slipway-dock-01",
            "Drydock Property: Deepwater Commercial Marine Slipway",
            {"property_urn": "urn:drydock:property:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "deed_ref": "DEED-HARBOR-SLIP-42", "utility_metric_keys": ["3_phase_480v_power", "potable_water"]},
            ["## Property Infrastructure", "## Structural Load Rating", "## Maintenance Records"],
        ),
        (
            "facility-machine-shop-02",
            "Drydock Property: Precision CNC & Lathe Workshop",
            {"property_urn": "urn:drydock:property:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "deed_ref": "DEED-SHOP-EAST-09", "utility_metric_keys": ["compressed_air", "exhaust_hvac"]},
            ["## Machinery Layout", "## Environmental Controls", "## Equipment Log"],
        ),
        (
            "facility-timber-loft-03",
            "Drydock Property: Traditional Timber Loft & Spar Shed",
            {"property_urn": "urn:drydock:property:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "deed_ref": "DEED-LOFT-TIMBER-11", "utility_metric_keys": ["humidity_monitors", "fire_suppression"]},
            ["## Woodworking Floor", "## Wood Seasoning Racks", "## Structural Surveys"],
        ),
        (
            "facility-berth-pennant-04",
            "Drydock Property: Heavy Mooring Berth & Quay Wall",
            {"property_urn": "urn:drydock:property:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "deed_ref": "DEED-QUAY-BERTH-04", "utility_metric_keys": ["shore_power", "fender_inspections"]},
            ["## Berth Dimensions", "## Bollard Pull Certs", "## Mooring History"],
        ),
    ],
    "16-squadron": [
        (
            "vehicle-honda-accord",
            "Squadron Asset: 2017 Honda Accord Touring",
            {"vin": "1HGCR2F83HA000000", "engine_hours": 3412.5, "telemetry_parquet_ref": "telemetry/squadron/vin_1hgcr.parquet"},
            ["## Vehicle Specification", "## Service Chronology", "## Telemetry Trends"],
        ),
        (
            "vehicle-service-van",
            "Squadron Asset: 2021 Ford Transit High-Roof Van",
            {"vin": "1FTBR1Y84MKA00000", "engine_hours": 1820.0, "telemetry_parquet_ref": "telemetry/squadron/vin_1ftbr.parquet"},
            ["## Commercial Upfitting", "## Powertrain Diagnostics", "## Scheduled Service"],
        ),
        (
            "vehicle-electric-cargo-bike",
            "Squadron Asset: Tern GSD S00 Cargo Bicycle",
            {"vin": "1TERN984210000000", "engine_hours": 420.0, "telemetry_parquet_ref": "telemetry/squadron/vin_tern.parquet"},
            ["## Battery Health Cycles", "## Drivetrain Wear", "## Urban Routes"],
        ),
        (
            "vehicle-marine-launch",
            "Squadron Asset: 22ft Diesel Workboat Launch",
            {"vin": "1YANM842918800000", "engine_hours": 890.0, "telemetry_parquet_ref": "telemetry/squadron/vin_yanmar.parquet"},
            ["## Engine Log", "## Hull Condition", "## Harbor Run History"],
        ),
    ],
    "17-supercargo": [
        (
            "gear-dell-server-node",
            "Supercargo Inventory: Dell PowerEdge R740 Server Node",
            {"serial_number": "SN-DELL-R740-9942", "mac_address": "00:1A:2B:3C:4D:5E", "warranty_expiry": "2027-10-15"},
            ["## Hardware Specification", "## Physical Location", "## Purchase Record"],
        ),
        (
            "gear-cisco-managed-switch",
            "Supercargo Inventory: Cisco Catalyst 48-Port PoE Switch",
            {"serial_number": "SN-CISCO-CAT-48P", "mac_address": "00:1A:2B:6F:8A:9B", "warranty_expiry": "2028-04-01"},
            ["## Port Allocations", "## Rack Mount Bin", "## Firmware State"],
        ),
        (
            "gear-fluke-thermal-camera",
            "Supercargo Inventory: Fluke Ti401 PRO Thermal Imager",
            {"serial_number": "SN-FLUKE-TI401-01", "mac_address": "00:1A:2B:11:22:33", "warranty_expiry": "2029-06-30"},
            ["## Calibration Standard", "## Sensor Enclosure", "## Field Deployments"],
        ),
        (
            "gear-polar-sensor-chest",
            "Supercargo Inventory: Polar H10 Bluetooth Biometric Sensor",
            {"serial_number": "SN-POLAR-H10-884", "mac_address": "00:1A:2B:44:55:66", "warranty_expiry": "2026-11-20"},
            ["## Electrode Condition", "## Battery Replacements", "## Pairing Registry"],
        ),
    ],
    "18-commonplace": [
        (
            "book-time-machine",
            "Commonplace Review: The Time Machine by H.G. Wells",
            {"isbn13": "9780451530707", "creator": "H.G. Wells", "shelf_state": "read", "rating": 4.5},
            ["## Literary Synopsis", "## Curated Quotations", "## Thematic Synthesis"],
        ),
        (
            "book-designing-data-intensive-apps",
            "Commonplace Review: Designing Data-Intensive Applications",
            {"isbn13": "9781449373320", "creator": "Martin Kleppmann", "shelf_state": "reference", "rating": 5.0},
            ["## Architectural Invariants", "## Replication & Consensus", "## Key Diagrams"],
        ),
        (
            "book-antifragile",
            "Commonplace Review: Antifragile: Things That Gain from Disorder",
            {"isbn13": "9781400067824", "creator": "Nassim Nicholas Taleb", "shelf_state": "read", "rating": 4.2},
            ["## Non-Linearity Principles", "## Convex Heuristics", "## Practical Application"],
        ),
        (
            "book-structure-interpretation-programs",
            "Commonplace Review: Structure and Interpretation of Computer Programs",
            {"isbn13": "9780262510875", "creator": "Harold Abelson and Gerald Jay Sussman", "shelf_state": "reference", "rating": 4.8},
            ["## Computational Abstraction", "## Metalinguistic Design", "## Exercise Notes"],
        ),
    ],
    "19-chantey": [
        (
            "podcast-ep42-sovereign-networks",
            "Chantey Broadcast: Episode 42 - Local-First Sovereign Networks",
            {"enclosure_url": "https://media.bosunpkm.com/audio/ep42.mp3", "duration_seconds": 3840.0, "transcript_cas": "urn:chantey:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"},
            ["## Episode Synopsis", "## Guest Dialogue", "## Audio Timeline"],
        ),
        (
            "podcast-ep43-marine-craft",
            "Chantey Broadcast: Episode 43 - Traditional Wooden Shipbuilding",
            {"enclosure_url": "https://media.bosunpkm.com/audio/ep43.mp3", "duration_seconds": 2950.0, "transcript_cas": "urn:chantey:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"},
            ["## Shipwright Interview", "## Timber Selection", "## Tool Lore"],
        ),
        (
            "podcast-ep44-spacetime-archives",
            "Chantey Broadcast: Episode 44 - Archival Preservation Across Centuries",
            {"enclosure_url": "https://media.bosunpkm.com/audio/ep44.mp3", "duration_seconds": 4120.0, "transcript_cas": "urn:chantey:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"},
            ["## Archivist Round-Table", "## Substrate Decay", "## Digital Permanence"],
        ),
        (
            "podcast-ep45-decentralized-finance",
            "Chantey Broadcast: Episode 45 - Plain Text Accounting & Double Entry",
            {"enclosure_url": "https://media.bosunpkm.com/audio/ep45.mp3", "duration_seconds": 3210.0, "transcript_cas": "urn:chantey:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"},
            ["## Accounting Invariants", "## Beancount Toolchains", "## Financial Autonomy"],
        ),
    ],
    "20-marquee": [
        (
            "cut-assembly-intro-sequence",
            "Marquee Video Cut: Title Sequence Rush Assembly",
            {"timecode_in": "00:01:00:00", "timecode_out": "00:02:30:15", "rush_bin": "Bin-01-Title-Seq"},
            ["## Shot Progression", "## Color Grading Notes", "## Audio Stems"],
        ),
        (
            "cut-assembly-shipyard-aerial",
            "Marquee Video Cut: B-Roll Drydock Drone Flyover",
            {"timecode_in": "00:05:12:10", "timecode_out": "00:06:45:00", "rush_bin": "Bin-02-Drone-Aerials"},
            ["## Camera Flight Path", "## Lighting Conditions", "## Stabilizer Metadata"],
        ),
        (
            "cut-assembly-machining-closeup",
            "Marquee Video Cut: 4K Macro Lathe Turning Shavings",
            {"timecode_in": "00:10:00:00", "timecode_out": "00:11:15:20", "rush_bin": "Bin-03-Macro-Lathe"},
            ["## Shutter Speed Profile", "## Coolant Flow Focus", "## Sound Design"],
        ),
        (
            "cut-assembly-closing-credits",
            "Marquee Video Cut: Motion Graphics End Slate",
            {"timecode_in": "00:45:00:00", "timecode_out": "00:47:00:00", "rush_bin": "Bin-04-End-Titles"},
            ["## Typography Hierarchy", "## Font Rendering", "## Roll Duration"],
        ),
    ],
}

# Auto-generate remaining realms 21-50 using standard schema definitions
def _populate_remaining_realm_definitions():
    base_specs = {
        "21-scrimshaw": ("cad_model_cas", "urn:scrimshaw:cad:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "gcode_profile", "prusa_petg_0.2", "toolpath_version", "2.1.0"),
        "22-traverse": ("geojson_feature", {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-122.4194, 37.7749]}}, "epsg_srid", 4326, "survey_datum", "WGS84"),
        "23-docent": ("doi", "10.1145/3318464.3389700", "bibtex_key", "shannon1948", "arxiv_id", "arXiv:2301.00001"),
        "24-proctor": ("docket_number", "1:26-cv-00123", "pacer_case_id", "PACER-99124", "statute_refs", ["17 U.S.C. 107"]),
        "25-ropewalk": ("repo_slug", "dotfiles-primary", "remote_origin", "git@github.com:bosun/dotfiles.git", "dotfile_target_path", "~/.config/zsh"),
        "26-gavel": ("committee_slug", "executive-steering", "meeting_date", "2026-09-17", "bylaws_uri", "https://bosunpkm.com/bylaws/v1", "motion_tallies", [{"title": "Approve charter", "ayes": 5, "nays": 0}]),
        "27-lineage": ("individual_urn", "urn:lineage:person:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "pedigree_branch", "maternal", "vital_dates", {"birth": "1920-04-12", "death": "1998-11-03"}, "gedcom_id", "@I001@"),
        "28-legacy": ("trust_ref", "TRUST-REVOCABLE-2026", "living_will_cas", "urn:legacy:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "executor_contact_urn", "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "durable_poa_hash", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        "29-arbor": ("taxonomic_species", "Quercus robur", "seed_vintage_year", 2024, "planting_zone", "Zone 7b", "soil_ph_optimal", 6.5),
        "30-the-glass": ("station_id", "STATION-NW-04", "barometric_hpa", 1013.25, "tide_gauge_urn", "urn:glass:tide:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "telemetry_parquet_ref", "telemetry/barometer.parquet"),
        "31-dispatch": ("sender_urn", "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "recipient_urn", "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "postmark_date", "2026-09-17", "courier_tracking", "1Z9999999999999999"),
        "32-registry": ("document_type", "passport", "issuing_jurisdiction", "US-CA", "expiry_date", "2034-05-20", "encrypted_credential_cas", "urn:registry:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"),
        "33-purser": ("billing_cadence", "monthly", "vendor_urn", "urn:purser:vendor:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "monthly_spend_usd", 49.99, "cancellation_sla", "30 days notice"),
        "34-cadence": ("streak_count_current", 42, "target_frequency", "daily", "ritual_window", "morning_routine", "best_streak", 120),
        "35-reckoning": ("decision_framework", "inversion_model", "pre_mortem_risk_tags", ["vendor_lockin", "spof"], "bias_audit_flags", ["confirmation_bias"]),
        "36-strongbox": ("key_algorithm", "Ed25519", "public_key_fingerprint", "SHA256:fingerprint", "hardware_token_serial", "YUBI-99421", "derivation_path", "m/44'/60'/0'/0/0"),
        "37-trajectory": ("role_title", "Principal Staff Engineer", "organization_urn", "urn:trajectory:org:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "tenure_start", "2022-01-15", "case_study_slugs", ["raft-consensus", "local-storage"]),
        "38-binnacle": ("theological_tradition", "christian_mysticism", "credo_axiom_key", "credo.logos.incarnate", "canonical_scripture_refs", ["John 1:1-14"]),
        "39-claim": ("patent_number", "US11223344B2", "jurisdiction_office", "USPTO", "filing_date", "2023-04-12", "prior_art_urns", ["urn:claim:prior:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"]),
        "40-tribute": ("recipient_contact_urn", "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "sizing_chart_profile", {"shirt": "L", "ring_size": 10}, "reciprocity_balance", 1.0),
        "41-weft": ("garment_category", "outerwear", "textile_composition", {"wool": 80, "cashmere": 20}, "care_wash_spec", "Dry clean only", "tailoring_measurements", {"chest_cm": 104, "sleeve_cm": 65}),
        "42-reverie": ("dream_motif_tags", ["ocean_voyage", "library"], "lucidity_level", 4, "sleep_stage_anchor", "REM"),
        "43-provenance": ("appraisal_usd", 12500.0, "chain_of_custody_urns", ["urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"], "edition_number", "1/25", "authenticity_cert_cas", "urn:provenance:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"),
        "44-menagerie": ("species_breed", "Canis lupus familiaris", "microchip_hex_id", "985141000123456", "vet_clinic_urn", "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "vaccination_schedule", [{"vaccine": "Rabies", "due_date": "2027-05-15"}]),
        "45-muster": ("rally_point_coordinates", [-122.4194, 37.7749], "bug_out_tier", "72h_evac", "ration_expiry_date", "2028-09-01", "comms_frequency_mhz", 146.52),
        "46-breadboard": ("schematic_cas", "urn:breadboard:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "pcb_revision", "Rev C.2", "gpio_pinout_map", {"I2C_SDA": "GPIO21"}, "operating_voltage_vdc", 3.3),
        "47-pavilion": ("run_of_show_steps", [{"cue_time": "09:00", "activity": "Registration"}, {"cue_time": "10:00", "activity": "Keynote"}], "venue_reservation_urn", "urn:pavilion:venue:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "headcount_target", 150),
        "48-charthouse": ("campaign_lore_node", "lore.third_age.fall_of_gondolin", "timeline_epoch", "Second Age of the Sun", "scene_binder_ref", "BINDER-ACT-2"),
        "49-commonwealth": ("initiative_name", "Bay Area Tool Library", "hours_logged", 8.5, "volunteer_urn", "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43", "mutual_aid_batch_id", "BATCH-2026-W38"),
        "50-relay": ("dead_man_interval_days", 30, "heartbeat_received_at", "2026-09-17T08:00:00Z", "master_recovery_key_cas", "urn:relay:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"),
    }

    for r_key, tuple_vals in base_specs.items():
        r_name = r_key.split("-", 1)[1]
        attrs = {}
        for i in range(0, len(tuple_vals), 2):
            attrs[tuple_vals[i]] = tuple_vals[i+1]

        notes = []
        for idx in range(1, 5):
            slug = f"{r_name}-synthetic-entry-{idx:02d}"
            title = f"{r_name.capitalize()} Synthetic Note #{idx:02d}"
            # shallow copy attributes with variations
            custom_attrs = dict(attrs)
            if "edition_number" in custom_attrs:
                custom_attrs["edition_number"] = f"{idx}/25"
            if "hours_logged" in custom_attrs:
                custom_attrs["hours_logged"] = 4.0 + idx
            if "dead_man_interval_days" in custom_attrs:
                custom_attrs["dead_man_interval_days"] = 30 + idx * 5
            headings = [
                f"## {r_name.capitalize()} Narrative Overview",
                f"## Specification Details",
                f"## Verification & Integration Records",
            ]
            notes.append((slug, title, custom_attrs, headings))
        REALM_NOTE_DEFINITIONS[r_key] = notes


_populate_remaining_realm_definitions()


class SyntheticVaultBuilder:
    def __init__(self, target_dir: pathlib.Path = _VAULT_DIR):
        self.target_dir = target_dir
        self.notes: Dict[str, Dict[str, Any]] = {}  # key: note_key, value: dict

    def generate_vault(self) -> Dict[str, Any]:
        """Generate all 200 notes across 50 realms and write to disk."""
        self.target_dir.mkdir(parents=True, exist_ok=True)
        _, validators = build_schema_registry()

        # Step 1: Initialize all note structures and assign UUIDv7
        for realm_key, note_specs in REALM_NOTE_DEFINITIONS.items():
            realm_name = realm_key.split("-", 1)[1]
            realm_dir = self.target_dir / realm_key
            realm_dir.mkdir(parents=True, exist_ok=True)

            for slug, title, attrs, headings in note_specs:
                full_key = f"{realm_name}:{slug}"
                note_uuid = generate_uuidv7(full_key)
                note_id = f"urn:uuid:{note_uuid}"

                self.notes[full_key] = {
                    "realm_key": realm_key,
                    "realm": realm_name,
                    "slug": slug,
                    "title": title,
                    "uuid": note_uuid,
                    "id": note_id,
                    "attrs": dict(attrs),
                    "headings": headings,
                    "relations": {},
                }

        # Step 2: Wire cross-realm relationships
        # Key references
        ada_uuid = self.notes["yeoman:contact-ada-lovelace"]["uuid"]
        babbage_uuid = self.notes["yeoman:contact-charles-babbage"]["uuid"]
        hopper_uuid = self.notes["yeoman:contact-grace-hopper"]["uuid"]
        vance_uuid = self.notes["yeoman:contact-dr-elena-vance"]["uuid"]

        tx_dell_uuid = self.notes["quartermaster:tx-server-rack-purchase"]["uuid"]
        tx_slipway_uuid = self.notes["quartermaster:tx-slipway-winch-lubricant"]["uuid"]
        tx_retainer_uuid = self.notes["quartermaster:tx-consulting-retainer-disbursement"]["uuid"]

        event_symposium_uuid = self.notes["logbook:event-quarterly-symposium"]["uuid"]
        event_townhall_uuid = self.notes["logbook:event-community-town-hall"]["uuid"]

        # Wire requirement 1: Trice task -> Yeoman contact (assignedToContact)
        self.notes["trice:task-archive-ingest"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{ada_uuid}"
        self.notes["trice:task-quarterly-tax-prep"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{babbage_uuid}"
        self.notes["trice:task-campaign-worldbuilding"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{hopper_uuid}"
        self.notes["trice:task-cardiac-vitals-review"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{vance_uuid}"

        # Wire requirement 2: Supercargo gear -> Quartermaster tx (purchasedViaTx)
        self.notes["supercargo:gear-dell-server-node"]["relations"]["purchasedViaTx"] = f"urn:qtm:tx:{tx_dell_uuid}"
        self.notes["supercargo:gear-cisco-managed-switch"]["relations"]["purchasedViaTx"] = f"urn:qtm:tx:{tx_dell_uuid}"
        self.notes["supercargo:gear-fluke-thermal-camera"]["relations"]["purchasedViaTx"] = f"urn:qtm:tx:{tx_retainer_uuid}"
        self.notes["supercargo:gear-polar-sensor-chest"]["relations"]["purchasedViaTx"] = f"urn:qtm:tx:{tx_dell_uuid}"

        # Wire requirement 3: Careen stage-gate cards derive from Trice tasks.
        # campaign_lore_node is a Charthouse delta attribute, not a $pkm.relations verb.
        campaign_task_uuid = self.notes["trice:task-campaign-worldbuilding"]["uuid"]
        archive_task_uuid = self.notes["trice:task-archive-ingest"]["uuid"]
        self.notes["careen:project-worldbuilding-refit"]["relations"][
            "actionItemDerivedFrom"
        ] = f"urn:trice:task:{campaign_task_uuid}"
        self.notes["careen:project-vault-scaffolding"]["relations"][
            "actionItemDerivedFrom"
        ] = f"urn:trice:task:{archive_task_uuid}"

        # Wire requirement 4: Pratique vitals -> Yeoman provider (consultedProvider)
        self.notes["pratique:vitals-cardiology-panel"]["relations"]["consultedProvider"] = f"urn:yeoman:contact:{vance_uuid}"
        self.notes["pratique:vitals-respiratory-capacity"]["relations"]["consultedProvider"] = f"urn:yeoman:contact:{vance_uuid}"
        self.notes["pratique:vitals-sleep-architecture"]["relations"]["consultedProvider"] = f"urn:yeoman:contact:{vance_uuid}"
        self.notes["pratique:vitals-blood-pressure-panel"]["relations"]["consultedProvider"] = f"urn:yeoman:contact:{vance_uuid}"

        # Wire additional interconnections across other realms
        # Bosun notes assigned to contact
        self.notes["bosun:offline-first-sovereign-graph"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{ada_uuid}"
        self.notes["bosun:content-addressed-storage-cas"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{hopper_uuid}"

        # Drydock purchase via Quartermaster tx
        self.notes["drydock:facility-slipway-dock-01"]["relations"]["purchasedViaTx"] = f"urn:qtm:tx:{tx_slipway_uuid}"

        # Logbook events attended
        self.notes["logbook:journal-2026-09-16"]["relations"]["attendedEvent"] = f"urn:logbook:event:{event_symposium_uuid}"
        self.notes["logbook:journal-2026-09-17"]["relations"]["attendedEvent"] = f"urn:logbook:event:{event_townhall_uuid}"

        # Yeoman contacts consultations
        self.notes["yeoman:contact-ada-lovelace"]["relations"]["consultedProvider"] = f"urn:yeoman:contact:{vance_uuid}"

        # Harbor, Primer, Squadron, Gavel, Commonwealth, Relay assigned contacts
        self.notes["harbor:route-home-portal"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{ada_uuid}"
        self.notes["primer:flashcard-dijkstra-shortest-path"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{hopper_uuid}"
        self.notes["squadron:vehicle-honda-accord"]["relations"]["assignedToContact"] = f"urn:yeoman:contact:{babbage_uuid}"

        # Wire remaining realms to have valid target relations
        for full_key, note in self.notes.items():
            r = note["realm"]
            if not note["relations"]:
                # Provide a default valid relation to an existing note in the vault
                if r in ("proctor", "gavel", "commonwealth", "relay", "menagerie", "tribute", "dispatch", "pavilion", "muster"):
                    note["relations"]["assignedToContact"] = f"urn:yeoman:contact:{ada_uuid}"
                elif r in ("press", "scrimshaw", "breadboard", "weft"):
                    note["relations"]["purchasedViaTx"] = f"urn:qtm:tx:{tx_dell_uuid}"
                elif r in ("cadence", "reverie"):
                    note["relations"]["attendedEvent"] = f"urn:logbook:event:{event_symposium_uuid}"
                elif r in ("docent", "passage", "galley", "embers", "chantey", "marquee", "traverse"):
                    note["relations"]["assignedToContact"] = f"urn:yeoman:contact:{hopper_uuid}"
                else:
                    note["relations"]["assignedToContact"] = f"urn:yeoman:contact:{babbage_uuid}"

        # Update note attributes containing URNs to ensure they point to existing notes
        # Drydock property_urn -> facility-slipway-dock-01 UUID
        dock_uuid = self.notes["drydock:facility-slipway-dock-01"]["uuid"]
        for k in ("drydock:facility-slipway-dock-01", "drydock:facility-machine-shop-02", "drydock:facility-timber-loft-03", "drydock:facility-berth-pennant-04"):
            self.notes[k]["attrs"]["property_urn"] = f"urn:drydock:property:{dock_uuid}"

        # Milestone URN in Careen -> Careen project UUID
        careen_milestone_uuid = self.notes["careen:project-worldbuilding-refit"]["uuid"]
        for k in self.notes:
            if k.startswith("careen:"):
                self.notes[k]["attrs"]["milestone_urn"] = f"urn:careen:milestone:{careen_milestone_uuid}"

        # Press CAS -> Embers media hash
        press_cas_uuid = self.notes["embers:media-photo-slipway-refit"]["uuid"]
        for k in self.notes:
            if k.startswith("press:"):
                self.notes[k]["attrs"]["vector_asset_cas"] = f"urn:press:cas:{press_cas_uuid}"

        # Legacy executor_contact_urn -> Vance UUID
        # Lineage individual_urn -> Ada UUID
        # Dispatch sender / recipient -> Ada / Babbage
        # Commonwealth volunteer_urn -> Hopper
        # Pavilion venue_reservation_urn -> Dock UUID
        for k, n in self.notes.items():
            if n["realm"] == "legacy":
                n["attrs"]["executor_contact_urn"] = f"urn:yeoman:contact:{vance_uuid}"
            elif n["realm"] == "lineage":
                n["attrs"]["individual_urn"] = f"urn:lineage:person:{ada_uuid}"
            elif n["realm"] == "dispatch":
                n["attrs"]["sender_urn"] = f"urn:yeoman:contact:{ada_uuid}"
                n["attrs"]["recipient_urn"] = f"urn:yeoman:contact:{babbage_uuid}"
            elif n["realm"] == "commonwealth":
                n["attrs"]["volunteer_urn"] = f"urn:yeoman:contact:{hopper_uuid}"
            elif n["realm"] == "pavilion":
                n["attrs"]["venue_reservation_urn"] = f"urn:pavilion:venue:{dock_uuid}"
            elif n["realm"] == "tribute":
                n["attrs"]["recipient_contact_urn"] = f"urn:yeoman:contact:{ada_uuid}"
            elif n["realm"] == "menagerie":
                n["attrs"]["vet_clinic_urn"] = f"urn:yeoman:contact:{vance_uuid}"
            elif n["realm"] == "provenance":
                n["attrs"]["chain_of_custody_urns"] = [f"urn:yeoman:contact:{ada_uuid}"]
            elif n["realm"] == "claim":
                n["attrs"]["prior_art_urns"] = [f"urn:claim:prior:{self.notes['bosun:offline-first-sovereign-graph']['uuid']}"]
            elif n["realm"] == "purser":
                n["attrs"]["vendor_urn"] = f"urn:purser:vendor:{self.notes['quartermaster:tx-cloud-storage-subscription']['uuid']}"
            elif n["realm"] == "the-glass":
                n["attrs"]["tide_gauge_urn"] = f"urn:glass:tide:{dock_uuid}"
            elif n["realm"] == "trajectory":
                n["attrs"]["organization_urn"] = f"urn:trajectory:org:{dock_uuid}"

        # Step 3: Serialize and write every note
        validated_count = 0
        for full_key, n in self.notes.items():
            realm_key = n["realm_key"]
            validator = validators[realm_key]

            frontmatter = {
                "title": n["title"],
                **n["attrs"],
                "$pkm": {
                    "id": n["id"],
                    "realm": n["realm"],
                    "created_at": "2026-09-17T10:00:00Z",
                    "updated_at": "2026-09-17T11:00:00Z",
                    "relations": n["relations"],
                }
            }

            # Schema validation
            validator.validate(frontmatter)
            validated_count += 1

            # Format markdown document
            yaml_str = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
            headings_text = "\n\n".join(
                f"{h}\nDemonstration content for {n['title']} within the sovereign knowledge graph."
                for h in n["headings"]
            )
            body = (
                f"# {n['title']}\n\n"
                f"Synthetic fixture record for realm `{n['realm']}`.\n\n"
                f"{headings_text}\n\n"
                f"## Transcluded Context\n"
                f"![[{n['realm']}/{n['slug']}#summary]]\n"
            )

            file_content = f"---\n{yaml_str}---\n\n{body}"
            target_file = self.target_dir / realm_key / f"{n['slug']}.md"
            target_file.write_text(file_content, encoding="utf-8")

        parquet_paths = write_telemetry_partitions(self.target_dir)
        print(f"Successfully generated and validated {validated_count} synthetic notes in {self.target_dir}")
        print(f"Wrote {len(parquet_paths)} telemetry Parquet partitions referenced by notes")
        return self.notes


def _extract_frontmatter(content: str) -> str:
    """Return the YAML frontmatter block from a markdown note."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("Note does not begin with frontmatter marker '---'")
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "".join(lines[1:idx])
    raise ValueError("Note is missing closing frontmatter marker '---'")


def collect_telemetry_parquet_refs(vault_dir: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    """Discover parquet partitions referenced by synthetic vault notes.

    Returns a mapping of relative parquet path -> {realm, note, attrs} for the
    first note that referenced each file. Paths are relative to ``vault_dir``.
    """
    jobs: Dict[str, Dict[str, Any]] = {}
    for md_path in sorted(vault_dir.rglob("*.md")):
        try:
            fm_text = _extract_frontmatter(md_path.read_text(encoding="utf-8"))
            data = yaml.safe_load(fm_text) or {}
        except (ValueError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        ref = data.get("telemetry_parquet_ref")
        if not ref:
            telemetry = data.get("telemetry")
            if isinstance(telemetry, dict):
                ref = telemetry.get("parquet_ref")
        if not ref or not isinstance(ref, str):
            continue
        if ref in jobs:
            continue
        pkm = data.get("$pkm") or {}
        jobs[ref] = {
            "realm": pkm.get("realm", ""),
            "note": str(md_path.relative_to(vault_dir)),
            "attrs": data,
        }
    return jobs


def _sample_rows_for_partition(rel_path: str, realm: str, attrs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a small PLAIN-encoded sample batch matching the realm contract."""
    stem = pathlib.PurePosixPath(rel_path.replace("\\", "/")).stem
    base_ts = 1726588800000000
    normalized = (realm or "").replace("-", "_")

    if normalized == "pratique":
        metric_by_stem = {
            "cardiac_hrv": ("heart_rate", "bpm"),
            "pulmonary": ("fev1", "L"),
            "sleep_stages": ("sleep_stage", "stage"),
            "abpm": ("systolic_bp", "mmHg"),
        }
        metric_type, unit = metric_by_stem.get(stem, ("heart_rate", "bpm"))
        sensor_id = str(attrs.get("sensor_source") or "synthetic-sensor")
        return [
            {
                "timestamp_utc": base_ts + (i * 1_000_000),
                "metric_type": metric_type,
                "value": 70.0 + (i * 1.5),
                "unit": unit,
                "sensor_id": sensor_id,
            }
            for i in range(5)
        ]

    if normalized == "squadron":
        vin = str(attrs.get("vin") or f"SYNTHETIC-{stem}")
        engine_hours = float(attrs.get("engine_hours") or 100.0)
        return [
            {
                "timestamp_utc": base_ts + (i * 1_000_000),
                "vin": vin,
                "engine_hours": engine_hours + i,
                "pid_code": "010C",
                "raw_value": 2000.0 + (i * 100.0),
            }
            for i in range(5)
        ]

    if normalized in ("the_glass",):
        station_id = str(attrs.get("station_id") or "STATION-NW-04")
        barometric = float(attrs.get("barometric_hpa") or 1013.25)
        return [
            {
                "timestamp_utc": base_ts + (i * 1_000_000),
                "station_id": station_id,
                "barometric_hpa": barometric + (i * 0.2),
                "tidal_height_m": 1.2 + (i * 0.1),
            }
            for i in range(5)
        ]

    raise ValueError(f"No telemetry Parquet contract for realm {realm!r} (ref {rel_path})")


def write_telemetry_partitions(vault_dir: pathlib.Path) -> List[pathlib.Path]:
    """Write sample Parquet partitions for every note-referenced telemetry path."""
    from scripts.parquet_codec import fields_from_record_contract, write_parquet_table

    contract_path = _REPO_ROOT / "schemas" / "v1" / "telemetry" / "parquet-contracts.schema.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    jobs = collect_telemetry_parquet_refs(vault_dir)
    written: List[pathlib.Path] = []
    for rel_path, job in jobs.items():
        realm = job["realm"]
        try:
            columns = fields_from_record_contract(contract, realm)
        except ValueError as exc:
            raise ValueError(
                f"Note {job['note']} references {rel_path} but realm {realm!r} "
                "has no Parquet column contract"
            ) from exc
        dest = vault_dir / pathlib.PurePosixPath(rel_path)
        rows = _sample_rows_for_partition(rel_path, realm, job["attrs"])
        write_parquet_table(dest, columns, rows)
        written.append(dest)
    return written


if __name__ == "__main__":
    builder = SyntheticVaultBuilder()
    builder.generate_vault()
