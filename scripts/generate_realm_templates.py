"""scripts/generate_realm_templates.py
Generates 50 canonical realm starter templates for Obsidian and Markdown
under templates/realms/<realm>.template.md using mustache/jinja variables:
  - {{ uuidv7 }}
  - {{ date_utc }}
  - {{ title }}
"""

from __future__ import annotations

import json
import pathlib
import yaml

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "templates" / "realms"

REALM_SPECS = {
    "01-bosun": (
        "bosun",
        {
            "zettel_type": "concept",
            "wikilinks": [],
            "ast_version": "1.0.0",
        },
        "Atomic zettel note capturing modular concepts within the sovereign knowledge graph.",
        [
            "## Concept Overview",
            "## Atomic Insights",
            "## Transcluded Context",
            "## References & Connections",
        ],
    ),
    "02-yeoman": (
        "yeoman",
        {
            "cadence_days": 14,
            "channels": [],
            "last_contact_date": "{{ date_utc }}",
        },
        "Personal CRM dossier maintaining interpersonal connection cadence and communication channels.",
        [
            "## Contact Overview",
            "## Interaction Log",
            "## Communication Channels",
            "## Follow-up & Next Actions",
        ],
    ),
    "03-trice": (
        "trice",
        {
            "task_state": "pending",
            "priority": "p2",
            "recurrence_rule": "",
        },
        "Actionable GTD task specification tracking state transitions and delivery commitments.",
        [
            "## Task Scope & Objectives",
            "## Action Checklist",
            "## Dependencies & Blockers",
            "## Status Log",
        ],
    ),
    "04-logbook": (
        "logbook",
        {
            "journal_date": "2026-09-17",
            "agenda_blocks": [],
            "transclusion_anchors": [],
        },
        "Daily journal scratchpad capturing chronological reflections, agenda blocks, and review notes.",
        [
            "## Daily Overview",
            "## Agenda & Scheduled Blocks",
            "## Notes & Scratchpad",
            "## Daily Reflection & Review",
        ],
    ),
    "05-quartermaster": (
        "quartermaster",
        {
            "beancount_account": "Assets:Bank:Checking",
            "tx_hash": "",
            "currency_code": "USD",
        },
        "Double-entry accounting record mapping transactions to Beancount accounts and ledger journals.",
        [
            "## Transaction Overview",
            "## Account Postings",
            "## Receipts & Verification",
            "## Reconciliation Notes",
        ],
    ),
    "06-harbor": (
        "harbor",
        {
            "slug": "getting-started",
            "edge_route": "/getting-started",
            "render_template": "docs-page",
        },
        "Web publishing ingress manifest configuring edge routes and zero-JS template rendering.",
        [
            "## Route Parameters",
            "## Ingress & Caching Policy",
            "## Page Body Content",
            "## Deployment Log",
        ],
    ),
    "07-press": (
        "press",
        {
            "sku": "PRESS-001",
            "vector_asset_cas": "urn:press:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "cut_sheet_spec": {
                "width_mm": 210,
                "height_mm": 297,
            },
        },
        "Print-on-demand cut sheet specification tracking vector assets, media substrates, and SKUs.",
        [
            "## Print Specifications",
            "## Vector Asset Reference",
            "## Cut Sheet & Finishing",
            "## Quality & Production Notes",
        ],
    ),
    "08-embers": (
        "embers",
        {
            "exif_payload": {
                "iso": 100,
                "focal_length": "50mm",
            },
            "media_hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "codec": "image/jpeg",
        },
        "Digital media asset record preserving content-addressed hashes, EXIF metadata, and preservation notes.",
        [
            "## Asset Summary",
            "## Technical Metadata & EXIF",
            "## Tagging & Subject Context",
            "## Preservation & Archive Log",
        ],
    ),
    "09-careen": (
        "careen",
        {
            "kanban_stage": "backlog",
            "sprint_ref": "sprint-01",
            "milestone_urn": "urn:careen:milestone:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
        },
        "Project management stage-gate card tracking sprint refits, milestones, and kanban progression.",
        [
            "## Project Objectives",
            "## Stage-Gate Deliverables",
            "## Kanban Coordination",
            "## Retrospective & Outcomes",
        ],
    ),
    "10-primer": (
        "primer",
        {
            "spaced_interval_days": 1.0,
            "ease_factor": 2.5,
            "skill_node": "core.concept",
        },
        "Spaced repetition flashcard and syllabus entry structuring deliberate learning and recall intervals.",
        [
            "## Concept & Principles",
            "## Recall Prompts & Exercises",
            "## Practical Examples",
            "## Revision History",
        ],
    ),
    "11-passage": (
        "passage",
        {
            "transit_mode": "rail",
            "booking_ref": "PASS-001",
            "waypoints": [],
        },
        "Travel passage itinerary tracking booking references, transit modes, waypoints, and packing logistics.",
        [
            "## Itinerary Overview",
            "## Booking & Ticket Reference",
            "## Waypoints & Schedule",
            "## Travel Logistics & Packing",
        ],
    ),
    "12-galley": (
        "galley",
        {
            "servings": 4,
            "prep_time_minutes": 30,
            "ingredients_schema": [],
        },
        "Culinary recipe card standardizing ingredient schemas, prep time, servings, and cooking procedures.",
        [
            "## Recipe Overview",
            "## Ingredients",
            "## Culinary Method",
            "## Notes & Modifications",
        ],
    ),
    "13-pratique": (
        "pratique",
        {
            "fhir_code": "8867-4",
            "sensor_source": "manual",
            "telemetry_parquet_ref": "telemetry/pratique/heart_rate.parquet",
        },
        "Health and biometric record linking clinical FHIR coding with local telemetry parquet data.",
        [
            "## Metric Overview",
            "## Clinical & Sensor Spec",
            "## Observations & Trends",
            "## Clinical Notes",
        ],
    ),
    "14-tactician": (
        "tactician",
        {
            "sport_type": "sailing",
            "split_metrics": {
                "speed_target_knots": 6.5,
            },
            "monte_carlo_preset": "wind_shift_envelope",
        },
        "Athletic performance and tactical simulation record calculating split metrics and strategy projections.",
        [
            "## Session Strategy",
            "## Target Split Metrics",
            "## Performance Telemetry",
            "## Post-Session Analysis",
        ],
    ),
    "15-drydock": (
        "drydock",
        {
            "property_urn": "urn:drydock:property:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "deed_ref": "DEED-001",
            "utility_metric_keys": [],
        },
        "Real estate and physical property dossier maintaining maintenance logs, deeds, and utility metrics.",
        [
            "## Property Overview",
            "## Maintenance & Service Orders",
            "## Utility Telemetry",
            "## Legal & Deed Documentation",
        ],
    ),
    "16-squadron": (
        "squadron",
        {
            "vin": "1HGCR2F83HA000000",
            "engine_hours": 0.0,
            "telemetry_parquet_ref": "telemetry/squadron/diagnostics.parquet",
        },
        "Vehicle and fleet asset record cataloging VINs, operational engine hours, and diagnostic telemetry.",
        [
            "## Vehicle Specification",
            "## Service & Maintenance Log",
            "## Diagnostic Telemetry",
            "## Operational Status",
        ],
    ),
    "17-supercargo": (
        "supercargo",
        {
            "serial_number": "SN-000001",
            "mac_address": "00:1B:44:11:3A:B7",
            "warranty_expiry": "2028-12-31",
        },
        "Physical hardware inventory record tracking serial numbers, network addresses, and warranties.",
        [
            "## Equipment Specifications",
            "## Location & Custody",
            "## Warranty & Maintenance Coverage",
            "## Inspection Log",
        ],
    ),
    "18-commonplace": (
        "commonplace",
        {
            "isbn13": "9780000000000",
            "creator": "Author Name",
            "shelf_state": "to_read",
            "rating": 5,
        },
        "Personal media and literature entry storing ISBN metadata, reading shelf states, and critical highlights.",
        [
            "## Work Overview",
            "## Core Concepts & Summary",
            "## Quotes & Highlights",
            "## Synthesis & Thoughts",
        ],
    ),
    "19-chantey": (
        "chantey",
        {
            "enclosure_url": "https://media.example.org/podcasts/episode-01.mp3",
            "duration_seconds": 1800.0,
            "transcript_cas": "urn:chantey:transcript:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
        },
        "Audio production and podcast note referencing audio enclosures, durations, and content-addressed transcripts.",
        [
            "## Episode Overview",
            "## Show Notes & Segments",
            "## Transcript & Key Quotes",
            "## References & Links",
        ],
    ),
    "20-marquee": (
        "marquee",
        {
            "timecode_in": "00:00:00:00",
            "timecode_out": "00:01:00:00",
            "rush_bin": "bin_01",
        },
        "Video and motion sequence note capturing in/out timecodes, rush bin organizations, and cut lists.",
        [
            "## Scene Description",
            "## Shot List & Timecodes",
            "## Edit Decision Notes",
            "## Review & Delivery",
        ],
    ),
    "21-scrimshaw": (
        "scrimshaw",
        {
            "cad_model_cas": "urn:scrimshaw:cad:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "gcode_profile": "default_profile",
            "toolpath_version": "v1.0.0",
        },
        "Digital fabrication and CAD record linking 3D geometry CAS references, toolpaths, and G-code profiles.",
        [
            "## Fabrication Goals",
            "## Tooling & Machine Parameters",
            "## Toolpath Configuration",
            "## Quality & Dimensional Verification",
        ],
    ),
    "22-traverse": (
        "traverse",
        {
            "geojson_feature": {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [0.0, 0.0],
                },
                "properties": {
                    "name": "Location Name",
                },
            },
            "epsg_srid": 4326,
            "survey_datum": "WGS84",
        },
        "Spatial survey record holding RFC 7946 GeoJSON geographic features, coordinate systems, and survey datums.",
        [
            "## Geographic Overview",
            "## Coordinates & Spatial Spec",
            "## Field Survey Log",
            "## Boundary Notes",
        ],
    ),
    "23-docent": (
        "docent",
        {
            "doi": "10.1000/182",
            "bibtex_key": "author2026",
            "arxiv_id": "2601.00001",
        },
        "Scholarly citation and academic research note linking DOIs, BibTeX keys, and arXiv preprints.",
        [
            "## Abstract & Research Questions",
            "## Bibliographic Data",
            "## Methodology & Findings",
            "## Critical Evaluation & Notes",
        ],
    ),
    "24-proctor": (
        "proctor",
        {
            "docket_number": "1:26-cv-00001",
            "pacer_case_id": "court-000001",
            "statute_refs": [],
        },
        "Legal matter and litigation dossier tracking court docket numbers, PACER case IDs, and statute citations.",
        [
            "## Matter Summary & Parties",
            "## Procedural Timeline",
            "## Statutory References & Legal Basis",
            "## Evidentiary Analysis",
        ],
    ),
    "25-ropewalk": (
        "ropewalk",
        {
            "repo_slug": "user/config",
            "remote_origin": "git@github.com:user/config.git",
            "dotfile_target_path": "~/.config",
        },
        "Software repository and dotfile specification orchestrating remotes, target paths, and workstation toolchains.",
        [
            "## Configuration Scope",
            "## Toolchain Requirements",
            "## Dotfile Linking Targets",
            "## Setup & Maintenance Scripts",
        ],
    ),
    "26-gavel": (
        "gavel",
        {
            "committee_slug": "steering-committee",
            "meeting_date": "2026-09-17",
            "bylaws_uri": "https://example.org/bylaws",
            "motion_tallies": [],
        },
        "Parliamentary record capturing governance committee minutes, motion tallies, and bylaws citations.",
        [
            "## Meeting Overview",
            "## Roll Call & Quorum",
            "## Motions & Voting Records",
            "## Action Items & Next Meeting",
        ],
    ),
    "27-lineage": (
        "lineage",
        {
            "individual_urn": "urn:lineage:individual:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "pedigree_branch": "direct",
            "vital_dates": {
                "birth": "1900-01-01",
                "death": "",
            },
            "gedcom_id": "I001",
        },
        "Genealogical pedigree record tracking ancestor vital statistics, GEDCOM identifiers, and family branches.",
        [
            "## Individual Biography",
            "## Vital Dates & Pedigree",
            "## Archival Citations & Sources",
            "## Descendants & Kinship",
        ],
    ),
    "28-legacy": (
        "legacy",
        {
            "trust_ref": "TRUST-001",
            "living_will_cas": "urn:legacy:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "executor_contact_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "durable_poa_hash": "0000000000000000000000000000000000000000000000000000000000000000",
        },
        "Estate planning and end-of-life document indexing trusts, living wills, executor URNs, and POAs.",
        [
            "## Instrument Overview",
            "## Fiduciary Appointments",
            "## Asset Schedule & Instructions",
            "## Verification & Custody",
        ],
    ),
    "29-arbor": (
        "arbor",
        {
            "taxonomic_species": "Quercus alba",
            "seed_vintage_year": 2026,
            "planting_zone": "7b",
            "soil_ph_optimal": 6.5,
        },
        "Botanical specimen and gardening record cataloging taxonomic species, vintage years, and planting zones.",
        [
            "## Specimen Overview",
            "## Horticultural Profile & Soil Requirements",
            "## Growth Timeline & Seasonal Care",
            "## Propagation & Yield Log",
        ],
    ),
    "30-the-glass": (
        "the-glass",
        {
            "station_id": "STATION-001",
            "barometric_hpa": 1013.25,
            "tide_gauge_urn": "urn:the-glass:station:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "telemetry_parquet_ref": "telemetry/the-glass/weather.parquet",
        },
        "Meteorological observation record archiving barometric pressure, tide gauge sensors, and weather logs.",
        [
            "## Observation Overview",
            "## Barometric & Tidal Data",
            "## Telemetry Sensor Readings",
            "## Atmospheric Analysis",
        ],
    ),
    "31-dispatch": (
        "dispatch",
        {
            "sender_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "recipient_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba44",
            "postmark_date": "2026-09-17",
            "courier_tracking": "TRACK-001",
        },
        "Epistolary and courier correspondence manifest recording senders, recipients, and tracking identifiers.",
        [
            "## Correspondence Overview",
            "## Routing & Courier Logistics",
            "## Dispatch Content",
            "## Chain of Custody & Receipt",
        ],
    ),
    "32-registry": (
        "registry",
        {
            "document_type": "identity_document",
            "issuing_jurisdiction": "US",
            "expiry_date": "2036-09-17",
            "encrypted_credential_cas": "urn:registry:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
        },
        "Civic bureaucracy and official credentials index cataloging document types, jurisdictions, and expiries.",
        [
            "## Credential Overview",
            "## Issuing Authority & Legal Basis",
            "## Validity & Expiration Schedule",
            "## Verification Procedures",
        ],
    ),
    "33-purser": (
        "purser",
        {
            "billing_cadence": "monthly",
            "vendor_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "monthly_spend_usd": 0.0,
            "cancellation_sla": "30_days",
        },
        "Subscription and recurring SaaS expense contract tracking monthly spends, vendor URNs, and cancellation SLAs.",
        [
            "## Subscription Details",
            "## Financial Terms & Cost Allocation",
            "## SLA & Cancellation Policy",
            "## Utilization Review",
        ],
    ),
    "34-cadence": (
        "cadence",
        {
            "streak_count_current": 0,
            "target_frequency": "daily",
            "ritual_window": "morning",
            "best_streak": 0,
        },
        "Habit formation and ritual discipline record measuring performance streaks, frequencies, and execution windows.",
        [
            "## Habit Definition & Cue",
            "## Ritual Protocol Steps",
            "## Streak Log & Metrics",
            "## Reflection & Obstacles",
        ],
    ),
    "35-reckoning": (
        "reckoning",
        {
            "decision_framework": "first_principles",
            "pre_mortem_risk_tags": [],
            "bias_audit_flags": [],
        },
        "Mental model and strategic decision record conducting structured pre-mortems and cognitive bias audits.",
        [
            "## Decision Statement & Context",
            "## Evaluated Alternatives",
            "## Pre-Mortem & Risk Analysis",
            "## Bias Audit & Final Decision",
        ],
    ),
    "36-strongbox": (
        "strongbox",
        {
            "key_algorithm": "ed25519",
            "public_key_fingerprint": "SHA256:0000000000000000000000000000000000000000000",
            "hardware_token_serial": "00000000",
            "derivation_path": "m/44'/0'/0'/0/0",
        },
        "Cryptographic identity record securing key algorithms, hardware tokens, and derivation paths.",
        [
            "## Cryptographic Spec",
            "## Public Key & Fingerprints",
            "## Hardware Enclave Settings",
            "## Key Lifecycle & Revocation Plan",
        ],
    ),
    "37-trajectory": (
        "trajectory",
        {
            "role_title": "Staff Engineer",
            "organization_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "tenure_start": "2026-01-01",
            "case_study_slugs": [],
        },
        "Career milestone and professional portfolio dossier documenting roles, organizations, and impact case studies.",
        [
            "## Position Overview",
            "## Strategic Deliverables & Outcomes",
            "## Case Studies & Portfolio Evidence",
            "## Growth & Future Milestones",
        ],
    ),
    "38-binnacle": (
        "binnacle",
        {
            "theological_tradition": "philosophical",
            "credo_axiom_key": "first_axiom",
            "canonical_scripture_refs": [],
        },
        "Philosophical credo and moral compass entry formalizing guiding axioms and spiritual/ethical traditions.",
        [
            "## Credo Axiom & Core Thesis",
            "## Philosophical Exegesis",
            "## Practical Applications",
            "## Canonical References",
        ],
    ),
    "39-claim": (
        "claim",
        {
            "patent_number": "US-0000000",
            "jurisdiction_office": "USPTO",
            "filing_date": "2026-09-17",
            "prior_art_urns": [],
        },
        "Intellectual property and patent claim record structuring independent claims, filing dates, and prior art.",
        [
            "## Invention Overview",
            "## Claims Specification",
            "## Prior Art Analysis",
            "## Prosecution Timeline",
        ],
    ),
    "40-tribute": (
        "tribute",
        {
            "recipient_contact_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "sizing_chart_profile": {
                "standard": "medium",
            },
            "reciprocity_balance": 0.0,
        },
        "Gift and occasion registry maintaining recipient profiles, sizing preferences, and reciprocity balances.",
        [
            "## Recipient Profile",
            "## Sizing & Preferences",
            "## Gift Ideas & Wishlist",
            "## Gift Exchange History",
        ],
    ),
    "41-weft": (
        "weft",
        {
            "garment_category": "outerwear",
            "textile_composition": {
                "material": "cotton",
                "percentage": 100,
            },
            "care_wash_spec": "machine_wash_cold",
            "tailoring_measurements": {
                "chest_cm": 100,
            },
        },
        "Wardrobe inventory and textile specification tracking fabric compositions, wash care, and tailoring measurements.",
        [
            "## Garment Profile",
            "## Textile & Care Instructions",
            "## Tailoring & Fit Spec",
            "## Wear & Maintenance Log",
        ],
    ),
    "42-reverie": (
        "reverie",
        {
            "dream_motif_tags": [],
            "lucidity_level": 1,
            "sleep_stage_anchor": "REM",
        },
        "Dream journal and introspective stream note cataloging dream motifs, lucidity levels, and sleep stage anchors.",
        [
            "## Dream Recall",
            "## Motifs & Archetypal Themes",
            "## Sleep Architecture & Lucidity",
            "## Introspective Reflection",
        ],
    ),
    "43-provenance": (
        "provenance",
        {
            "appraisal_usd": 0.0,
            "chain_of_custody_urns": [],
            "edition_number": "1/1",
            "authenticity_cert_cas": "urn:provenance:cert:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
        },
        "Fine art and antique provenance dossier maintaining valuation appraisals, chains of custody, and certs of authenticity.",
        [
            "## Item Description & Condition",
            "## Chain of Custody",
            "## Valuation & Appraisals",
            "## Authenticity & Historical Significance",
        ],
    ),
    "44-menagerie": (
        "menagerie",
        {
            "species_breed": "Canis familiaris",
            "microchip_hex_id": "0123456789ABCDEF",
            "vet_clinic_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "vaccination_schedule": [],
        },
        "Animal husbandry and pet health record tracking microchip IDs, veterinary clinics, and vaccination schedules.",
        [
            "## Animal Profile",
            "## Veterinary & Medical Care",
            "## Vaccination Schedule",
            "## Behavioral & Dietary Notes",
        ],
    ),
    "45-muster": (
        "muster",
        {
            "rally_point_coordinates": [0.0, 0.0],
            "bug_out_tier": "tier_1",
            "ration_expiry_date": "2028-09-17",
            "comms_frequency_mhz": 146.52,
        },
        "Emergency preparedness and muster plan recording rally coordinates, bug-out tiers, rations, and radio comms.",
        [
            "## Plan Overview & Protocols",
            "## Rally Points & Evacuation Routes",
            "## Emergency Rations & Gear Manifest",
            "## Communications Frequencies",
        ],
    ),
    "46-breadboard": (
        "breadboard",
        {
            "schematic_cas": "urn:breadboard:schematic:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "pcb_revision": "rev_A",
            "gpio_pinout_map": {
                "pin_1": "VCC",
                "pin_2": "GND",
            },
            "operating_voltage_vdc": 3.3,
        },
        "Electronics and circuit prototyping specification defining schematics, PCB revisions, and GPIO pinouts.",
        [
            "## Circuit Specifications",
            "## Power & Electrical Operating Envelope",
            "## GPIO Pinout & Interfaces",
            "## Test Bench & Bring-Up Notes",
        ],
    ),
    "47-pavilion": (
        "pavilion",
        {
            "run_of_show_steps": [],
            "venue_reservation_urn": "urn:pavilion:venue:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "headcount_target": 50,
        },
        "Event coordination and social gathering plan detailing run-of-show cue sheets, venues, and headcount targets.",
        [
            "## Event Overview",
            "## Venue & Logistics",
            "## Run of Show & Stage Schedule",
            "## Guest List & Coordination",
        ],
    ),
    "48-charthouse": (
        "charthouse",
        {
            "campaign_lore_node": "world_bible",
            "timeline_epoch": "first_age",
            "scene_binder_ref": "scene_001",
        },
        "Worldbuilding and narrative campaign lore node establishing timeline epochs, factions, and scene binders.",
        [
            "## Setting & Lore Overview",
            "## Timeline & Historical Chronology",
            "## Dramatis Personae & Factions",
            "## Scene Binder & Narrative Notes",
        ],
    ),
    "49-commonwealth": (
        "commonwealth",
        {
            "initiative_name": "Mutual Aid Initiative",
            "hours_logged": 0.0,
            "volunteer_urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "mutual_aid_batch_id": "BATCH-2026-01",
        },
        "Mutual aid and community service ledger recording volunteer hours, initiative names, and aid distribution batches.",
        [
            "## Initiative Overview",
            "## Volunteer Log & Contributions",
            "## Aid Distribution & Logistics",
            "## Community Impact & Notes",
        ],
    ),
    "50-relay": (
        "relay",
        {
            "dead_man_interval_days": 30,
            "heartbeat_received_at": "{{ date_utc }}",
            "master_recovery_key_cas": "urn:relay:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
        },
        "Digital afterlife and dead man's switch escrow maintaining heartbeat intervals and cryptographic recovery keys.",
        [
            "## Continuity Protocol",
            "## Heartbeat & Trigger Configuration",
            "## Trustee Distribution",
            "## Recovery & Handoff Procedures",
        ],
    ),
}


def build_template_content(realm_key: str) -> str:
    canonical_realm, delta_props, summary_desc, headings = REALM_SPECS[realm_key]

    frontmatter_lines = [
        "---",
        'title: "{{ title }}"',
    ]

    for prop_name, prop_val in delta_props.items():
        if isinstance(prop_val, (dict, list)):
            dumped = yaml.dump({prop_name: prop_val}, sort_keys=False).strip()
            frontmatter_lines.append(dumped)
        elif isinstance(prop_val, str) and "{{" in prop_val:
            frontmatter_lines.append(f'{prop_name}: "{prop_val}"')
        elif isinstance(prop_val, str):
            frontmatter_lines.append(f"{prop_name}: {json.dumps(prop_val)}")
        elif isinstance(prop_val, bool):
            frontmatter_lines.append(f"{prop_name}: {'true' if prop_val else 'false'}")
        else:
            frontmatter_lines.append(f"{prop_name}: {prop_val}")

    frontmatter_lines.extend([
        "$pkm:",
        '  id: "urn:uuid:{{ uuidv7 }}"',
        f"  realm: {canonical_realm}",
        '  created_at: "{{ date_utc }}"',
        '  updated_at: "{{ date_utc }}"',
        "  relations: {}",
        "---",
        "",
        "# {{ title }}",
        "",
        summary_desc,
        "",
    ])

    for heading in headings:
        frontmatter_lines.extend([
            heading,
            "",
            "<!-- Starter notes and context for this section -->",
            "",
        ])

    return "\n".join(frontmatter_lines)


def main() -> None:
    _TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for realm_key in REALM_SPECS:
        content = build_template_content(realm_key)
        target_path = _TEMPLATES_DIR / f"{realm_key}.template.md"
        target_path.write_text(content, encoding="utf-8")
        print(f"Generated: {target_path.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()
