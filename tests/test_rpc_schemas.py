"""tests/test_rpc_schemas.py
─────────────────────────
Unit test suite verifying:
  1. schemas/v1/rpc/error-envelope.schema.json
     - JSON-RPC 2.0 standard error response structure.
     - Adapter failure fixtures:
       - RPC timeout (-32603 Internal error)
       - Schema Validation Failed (-32000)
       - Lock contention (-32001 Vault Locked/Crypto Error)
     - Custom Bosun error codes:
       - -32000 (Schema Validation Failed)
       - -32001 (Vault Locked/Crypto Error)
       - -32002 (Orphan URN Detected)
  2. schemas/v1/rpc/event-payloads.schema.json
     - JSON-RPC 2.0 notification payloads across all 50 realms
       (e.g., cadence:habitHit, trice:taskStateChanged, quartermaster:txAppended).
     - Per-event *Payload $def fixtures for every event in the schema.
     - Harbormaster pub/sub event envelopes and stdio broadcast events.
     - Rejection of non-conforming payloads.

Usage:
  python tests/test_rpc_schemas.py
  python -m pytest tests/test_rpc_schemas.py -v
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest
from typing import Any, Dict

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_ERROR_SCHEMA_PATH = _SCHEMAS_DIR / "v1" / "rpc" / "error-envelope.schema.json"
_EVENT_SCHEMA_PATH = _SCHEMAS_DIR / "v1" / "rpc" / "event-payloads.schema.json"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID_PREFIX = "https://bosunpkm.com/schemas/"

_REQUIRED_50_REALMS = (
    "01-bosun", "02-yeoman", "03-trice", "04-logbook", "05-quartermaster",
    "06-harbor", "07-press", "08-embers", "09-careen", "10-primer",
    "11-passage", "12-galley", "13-pratique", "14-tactician", "15-drydock",
    "16-squadron", "17-supercargo", "18-commonplace", "19-chantey", "20-marquee",
    "21-scrimshaw", "22-traverse", "23-docent", "24-proctor", "25-ropewalk",
    "26-gavel", "27-lineage", "28-legacy", "29-arbor", "30-the-glass",
    "31-dispatch", "32-registry", "33-purser", "34-cadence", "35-reckoning",
    "36-strongbox", "37-trajectory", "38-binnacle", "39-claim", "40-tribute",
    "41-weft", "42-reverie", "43-provenance", "44-menagerie", "45-muster",
    "46-breadboard", "47-pavilion", "48-charthouse", "49-commonwealth", "50-relay"
)

# Fleet-adapter JSON-RPC 2.0 error fixtures (JSON objects per RFC 7159).
# Timeout uses reserved Internal error (-32603); schema failure and lock
# contention use Bosun server-error codes in the -32000..-32099 range.
FIXTURE_RPC_TIMEOUT = {
    "jsonrpc": "2.0",
    "id": "rpc-timeout-01",
    "error": {
        "code": -32603,
        "message": "Internal error",
        "data": {
            "reason": "timeout",
            "method": "trice.taskGet",
            "timeout_ms": 5000,
            "elapsed_ms": 5012,
        },
    },
}

FIXTURE_SCHEMA_FAILURE = {
    "jsonrpc": "2.0",
    "id": "rpc-schema-fail-01",
    "error": {
        "code": -32000,
        "message": "Schema Validation Failed",
        "data": {
            "schema": "https://bosunpkm.com/schemas/v1/realms/03-trice.schema.json",
            "path": "state",
            "errors": [
                "'working' is not one of ['pending', 'active', 'done', 'dropped', 'blocked']",
            ],
        },
    },
}

FIXTURE_LOCK_CONTENTION = {
    "jsonrpc": "2.0",
    "id": "rpc-lock-contend-01",
    "error": {
        "code": -32001,
        "message": "Vault Locked/Crypto Error",
        "data": {
            "vault_path": "fixtures/synthetic_vault",
            "reason": "lock_contention",
            "lock_state": "busy",
            "holder": "harbormaster-stdio",
        },
    },
}

ADAPTER_ERROR_FIXTURES = {
    "timeout": FIXTURE_RPC_TIMEOUT,
    "schema_failure": FIXTURE_SCHEMA_FAILURE,
    "lock_contention": FIXTURE_LOCK_CONTENTION,
}

# Realm prefix -> (method, params). Params satisfy the matching *Payload $def.
_REALM_NOTIFICATIONS = {
    "01-bosun": ("bosun:graphIndexed", {"vault_root": "/vault", "node_count": 200}),
    "02-yeoman": ("yeoman:interactionRecorded", {"contact_id": "ada", "occurred_at": "2026-09-17T10:00:00Z"}),
    "03-trice": ("trice:taskStateChanged", {"task_id": "t1", "new_state": "done"}),
    "04-logbook": ("logbook:entryAppended", {"path": "today.md", "date": "2026-09-17"}),
    "05-quartermaster": ("quartermaster:txAppended", {"account": "Assets:Cash", "amount": 50.0}),
    "06-harbor": ("harbor:siteBuilt", {"page_count": 12, "duration_ms": 340.5}),
    "07-press": ("press:cutSheetGenerated", {"sku": "SKU-01", "path": "cut.pdf"}),
    "08-embers": ("embers:exifIndexed", {"media_hash": "abc12345", "path": "photo.jpg"}),
    "09-careen": ("careen:stageMoved", {"task_id": "p1", "stage": "review"}),
    "10-primer": ("primer:cardReviewed", {"card_id": "c1", "rating": 5}),
    "11-passage": ("passage:waypointAdded", {"itinerary_id": "itin-1", "name": "London"}),
    "12-galley": ("galley:recipeScaled", {"recipe_id": "bread", "target_servings": 4}),
    "13-pratique": ("pratique:hl7Ingested", {"payload": "MSH|^~\\&|..."}),
    "14-tactician": ("tactician:simulationCompleted", {"race_id": "r1", "iterations": 500}),
    "15-drydock": ("drydock:maintenanceLogged", {"property_urn": "urn:drydock:property:01", "activity": "tune"}),
    "16-squadron": ("squadron:serviceLogged", {"vin": "1HGCR2F", "service_type": "oil_change"}),
    "17-supercargo": ("supercargo:binTransferred", {"item_id": "hw-1", "from_bin": "A1", "to_bin": "B2"}),
    "18-commonplace": ("commonplace:statusUpdated", {"slug": "book-1", "status": "read"}),
    "19-chantey": ("chantey:transcriptAppended", {"episode_id": "ep1", "timestamp_offset": 120.0}),
    "20-marquee": ("marquee:cutLogged", {"rush_bin": "binA", "timecode_in": "00:01:00", "timecode_out": "00:02:00"}),
    "21-scrimshaw": ("scrimshaw:cadModelLinked", {"part_slug": "bracket", "cad_model_cas": "urn:scrimshaw:cad:01"}),
    "22-traverse": ("traverse:geojsonIngested", {"srid": 4326}),
    "23-docent": ("docent:doiResolved", {"doi": "10.1000/182"}),
    "24-proctor": ("proctor:docketFiled", {"docket_number": "1:24-cv-001", "document_title": "Motion"}),
    "25-ropewalk": ("ropewalk:dotfilesSynced", {"repo_slug": "dotfiles/workstation"}),
    "26-gavel": ("gavel:minutesRecorded", {"committee_slug": "steering", "meeting_date": "2026-09-17"}),
    "27-lineage": ("lineage:individualAdded", {"name": "Eleanor", "pedigree_branch": "maternal"}),
    "28-legacy": ("legacy:trustVerified", {"trust_ref": "trust-2024"}),
    "29-arbor": ("arbor:amendmentRecorded", {"plot_id": "plot-1", "amendment_type": "compost"}),
    "30-the-glass": ("the_glass:tideLogged", {"tide_gauge_urn": "urn:glass:tide:01", "height_meters": 1.4}),
    "31-dispatch": ("dispatch:outboundLogged", {"sender_urn": "urn:yeoman:contact:01", "recipient_urn": "urn:yeoman:contact:02"}),
    "32-registry": ("registry:documentVaulted", {"document_type": "passport", "issuing_jurisdiction": "USA"}),
    "33-purser": ("purser:subscriptionLogged", {"active_only": True}),
    "34-cadence": ("cadence:habitHit", {"habit_id": "meditation", "date": "2026-09-17"}),
    "35-reckoning": ("reckoning:decisionLogged", {"decision_title": "Adopt SQLite", "framework": "cynefin"}),
    "36-strongbox": ("strongbox:fingerprintDerived", {"public_key": "ssh-ed25519 AAAAC3...", "key_algorithm": "ed25519"}),
    "37-trajectory": ("trajectory:milestoneAdded", {"role_title": "Staff Engineer", "milestone_title": "Led rewrite"}),
    "38-binnacle": ("binnacle:scriptureAnnotated", {"scripture_ref": "Book 1", "annotation": "Notes"}),
    "39-claim": ("claim:priorArtRecorded", {"patent_number": "US1000", "prior_art_urn": "urn:claim:prior:01"}),
    "40-tribute": ("tribute:giftLogged", {"recipient_contact_urn": "urn:yeoman:contact:01", "gift_item": "Pen"}),
    "41-weft": ("weft:tailoringLogged", {"garment_id": "tweed-01"}),
    "42-reverie": ("reverie:dreamLogged", {"description": "Sailing open seas"}),
    "43-provenance": ("provenance:appraisalAdded", {"item_urn": "urn:item:01", "appraisal_usd": 15000.0}),
    "44-menagerie": ("menagerie:vetVisitLogged", {"pet_id": "pet-01", "clinic_urn": "urn:clinic:01"}),
    "45-muster": ("muster:rationsChecked", {"tier": "72h"}),
    "46-breadboard": ("breadboard:schematicLinked", {"board_id": "esp32", "schematic_cas": "urn:cas:01"}),
    "47-pavilion": ("pavilion:cueSheetGenerated", {"event_id": "event-01"}),
    "48-charthouse": ("charthouse:loreNodeQueried", {"campaign_id": "camp-01"}),
    "49-commonwealth": ("commonwealth:hoursLogged", {"initiative_name": "Food Bank", "volunteer_urn": "urn:yeoman:contact:01", "hours": 3.5}),
    "50-relay": ("relay:heartbeatRecorded", {"channel_id": "ch-01", "timestamp": "2026-09-17T12:00:00Z"}),
}


def _subschema_validator(schema: Dict[str, Any], def_name: str) -> "Draft202012Validator":
    """Validator bound to a single $defs entry in the parent schema."""
    return Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$id": schema.get("$id", "") + f"#{def_name}",
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{def_name}",
        }
    )


def _method_to_payload_def(method: str) -> str:
    """Map ``realm:eventName`` onto the ``realmEventNamePayload`` $def."""
    realm, name = method.split(":", 1)
    realm_camel = "".join(
        word if index == 0 else word.title()
        for index, word in enumerate(realm.split("_"))
    )
    return f"{realm_camel}{name[0].upper()}{name[1:]}Payload"


def _payload_def_names(schema: Dict[str, Any]) -> list[str]:
    return sorted(
        name for name in schema.get("$defs", {}) if name.endswith("Payload")
    )


def _load_json(path: pathlib.Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestRpcErrorEnvelopeSchema(unittest.TestCase):
    """Verifies JSON-RPC 2.0 stdio error envelopes and Bosun custom error codes."""

    @classmethod
    def setUpClass(cls):
        if not _HAS_JSONSCHEMA:
            raise unittest.SkipTest("jsonschema not installed")
        cls.schema = _load_json(_ERROR_SCHEMA_PATH)
        cls.validator = Draft202012Validator(cls.schema)

    def test_schema_pins_draft_and_id(self):
        """error-envelope.schema.json pins Draft 2020-12 and canonical $id."""
        self.assertEqual(self.schema.get("$schema"), _DRAFT_2020_12)
        expected_id = _CANONICAL_ID_PREFIX + "v1/rpc/error-envelope.schema.json"
        self.assertEqual(self.schema.get("$id"), expected_id)

    def test_schema_passes_draft_2020_12_meta_schema(self):
        """error-envelope.schema.json passes check_schema."""
        Draft202012Validator.check_schema(self.schema)

    def test_valid_standard_jsonrpc_error_responses(self):
        """Standard JSON-RPC 2.0 error envelopes pass validation."""
        valid_samples = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                    "data": {"method": "unknown_method"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": "req-parse-01",
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                    "data": {"details": "Unexpected character at byte 14"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request"
                }
            },
            {
                "jsonrpc": "2.0",
                "id": "req-params-02",
                "error": {
                    "code": -32602,
                    "message": "Invalid params",
                    "data": {"param": "vault_root", "expected": "string"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": "req-internal-03",
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": {"reason": "stdio_pipe_closed"}
                }
            }
        ]
        for idx, sample in enumerate(valid_samples):
            with self.subTest(sample_idx=idx):
                self.validator.validate(sample)

    def test_adapter_error_fixtures_validate_against_error_envelope(self):
        """Timeout, schema failure, and lock contention fixtures match the envelope."""
        self.assertEqual(
            set(ADAPTER_ERROR_FIXTURES),
            {"timeout", "schema_failure", "lock_contention"},
        )
        for name, sample in ADAPTER_ERROR_FIXTURES.items():
            with self.subTest(fixture=name):
                self.validator.validate(sample)
                self.assertEqual(sample["jsonrpc"], "2.0")
                self.assertIn("id", sample)
                self.assertIsInstance(sample["error"]["code"], int)
                self.assertGreater(len(sample["error"]["message"]), 0)
                self.assertIsInstance(sample["error"]["data"], dict)

        self.assertEqual(FIXTURE_RPC_TIMEOUT["error"]["code"], -32603)
        self.assertEqual(FIXTURE_RPC_TIMEOUT["error"]["data"]["reason"], "timeout")
        self.assertEqual(FIXTURE_SCHEMA_FAILURE["error"]["code"], -32000)
        self.assertEqual(FIXTURE_LOCK_CONTENTION["error"]["code"], -32001)
        self.assertEqual(
            FIXTURE_LOCK_CONTENTION["error"]["data"]["reason"],
            "lock_contention",
        )

        _subschema_validator(self.schema, "schemaValidationErrorObject").validate(
            FIXTURE_SCHEMA_FAILURE["error"]
        )
        _subschema_validator(self.schema, "vaultLockedErrorObject").validate(
            FIXTURE_LOCK_CONTENTION["error"]
        )

    def test_custom_code_32000_schema_validation_failed(self):
        """Bosun code -32000 (Schema Validation Failed) validates cleanly."""
        sample = {
            "jsonrpc": "2.0",
            "id": "val-fail-01",
            "error": {
                "code": -32000,
                "message": "Schema Validation Failed",
                "data": {
                    "schema": "https://bosunpkm.com/schemas/v1/realms/02-yeoman.schema.json",
                    "path": "cadence_days",
                    "errors": [
                        "'fourteen' is not of type 'integer'",
                        "Missing required property 'channels'"
                    ]
                }
            }
        }
        self.validator.validate(sample)

        # Validate against subschema definition directly
        sub_schema = {
            "$schema": self.schema["$schema"],
            "$defs": self.schema["$defs"],
            "$ref": "#/$defs/schemaValidationErrorObject"
        }
        Draft202012Validator(sub_schema).validate(sample["error"])

    def test_custom_code_32001_vault_locked_crypto_error(self):
        """Bosun code -32001 (Vault Locked/Crypto Error) validates cleanly."""
        sample = {
            "jsonrpc": "2.0",
            "id": "vault-lock-01",
            "error": {
                "code": -32001,
                "message": "Vault Locked/Crypto Error",
                "data": {
                    "vault_path": "fixtures/synthetic_vault",
                    "reason": "passphrase_or_hardware_token_required",
                    "lock_state": "locked"
                }
            }
        }
        self.validator.validate(sample)

        sub_schema = {
            "$schema": self.schema["$schema"],
            "$defs": self.schema["$defs"],
            "$ref": "#/$defs/vaultLockedErrorObject"
        }
        Draft202012Validator(sub_schema).validate(sample["error"])

    def test_custom_code_32002_orphan_urn_detected(self):
        """Bosun code -32002 (Orphan URN Detected) validates cleanly."""
        sample = {
            "jsonrpc": "2.0",
            "id": "orphan-check-01",
            "error": {
                "code": -32002,
                "message": "Orphan URN Detected",
                "data": {
                    "urn": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba99",
                    "source_path": "03-trice/task-archive-ingest.md",
                    "predicate": "assignedToContact",
                    "realm": "trice"
                }
            }
        }
        self.validator.validate(sample)

        sub_schema = {
            "$schema": self.schema["$schema"],
            "$defs": self.schema["$defs"],
            "$ref": "#/$defs/orphanUrnErrorObject"
        }
        Draft202012Validator(sub_schema).validate(sample["error"])

    def test_error_envelope_invalid_payloads_rejected(self):
        """Malformed error envelopes are rejected by the schema."""
        invalid_samples = [
            # Missing jsonrpc member
            {"id": 1, "error": {"code": -32600, "message": "Error"}},
            # Wrong jsonrpc version
            {"jsonrpc": "1.0", "id": 1, "error": {"code": -32600, "message": "Error"}},
            # Missing error object
            {"jsonrpc": "2.0", "id": 1},
            # Missing code
            {"jsonrpc": "2.0", "id": 1, "error": {"message": "Error"}},
            # Non-integer code
            {"jsonrpc": "2.0", "id": 1, "error": {"code": "-32600", "message": "Error"}},
            # Empty message
            {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": ""}},
            # Non-object data
            {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "Error", "data": "bad"}},
            # Extra unexpected property
            {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "Error"}, "result": {}},
        ]
        for idx, sample in enumerate(invalid_samples):
            with self.subTest(invalid_sample_idx=idx):
                with self.assertRaises(jsonschema.ValidationError):
                    self.validator.validate(sample)


class TestRpcEventPayloadsSchema(unittest.TestCase):
    """Verifies event payload schemas for notifications across all 50 realms."""

    @classmethod
    def setUpClass(cls):
        if not _HAS_JSONSCHEMA:
            raise unittest.SkipTest("jsonschema not installed")
        cls.schema = _load_json(_EVENT_SCHEMA_PATH)
        cls.validator = Draft202012Validator(cls.schema)

    def test_schema_pins_draft_and_id(self):
        """event-payloads.schema.json pins Draft 2020-12 and canonical $id."""
        self.assertEqual(self.schema.get("$schema"), _DRAFT_2020_12)
        expected_id = _CANONICAL_ID_PREFIX + "v1/rpc/event-payloads.schema.json"
        self.assertEqual(self.schema.get("$id"), expected_id)

    def test_schema_passes_draft_2020_12_meta_schema(self):
        """event-payloads.schema.json passes check_schema."""
        Draft202012Validator.check_schema(self.schema)

    def test_explicit_harbormaster_notifications(self):
        """Verifies specific notification events requested in the prompt."""
        # 1. cadence:habitHit
        cadence_notification = {
            "jsonrpc": "2.0",
            "method": "cadence:habitHit",
            "params": {
                "habit_id": "morning-meditation",
                "date": "2026-09-17",
                "streak": 14,
                "notes": "20m zazen session"
            }
        }
        self.validator.validate(cadence_notification)

        # 2. trice:taskStateChanged
        trice_notification = {
            "jsonrpc": "2.0",
            "method": "trice:taskStateChanged",
            "params": {
                "task_id": "task-historical-archive-01",
                "previous_state": "pending",
                "new_state": "active",
                "updated_at": "2026-09-17T12:00:00Z"
            }
        }
        self.validator.validate(trice_notification)

        # 3. quartermaster:txAppended
        qtm_notification = {
            "jsonrpc": "2.0",
            "method": "quartermaster:txAppended",
            "params": {
                "tx_id": "tx-dell-server-rack",
                "account": "Assets:Bank:Checking",
                "amount": 142.50,
                "currency": "USD",
                "date": "2026-09-17",
                "tx_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            }
        }
        self.validator.validate(qtm_notification)

    def test_harbormaster_pubsub_event_envelope(self):
        """Harbormaster pub/sub domain event envelope format validates cleanly."""
        sample = {
            "event": "cadence:habitHit",
            "realm": "cadence",
            "timestamp": "2026-09-17T12:00:00Z",
            "payload": {
                "habit_id": "daily-review",
                "date": "2026-09-17"
            }
        }
        self.validator.validate(sample)

    def test_harbormaster_stdio_broadcast_envelope(self):
        """Harbormaster stdio broadcast notification format validates cleanly."""
        sample = {
            "name": "info.cadence.habit_logged",
            "when": "Habit status is recorded",
            "payload": {
                "habit_id": "morning-run"
            }
        }
        self.validator.validate(sample)

    def test_all_50_realms_have_valid_event_notifications(self):
        """Every one of the 50 realms has a conforming JSON-RPC 2.0 notification event."""
        self.assertEqual(len(_REALM_NOTIFICATIONS), 50)
        self.assertEqual(set(_REALM_NOTIFICATIONS), set(_REQUIRED_50_REALMS))

        for prefix in _REQUIRED_50_REALMS:
            with self.subTest(realm=prefix):
                method_name, params = _REALM_NOTIFICATIONS[prefix]
                notification = {
                    "jsonrpc": "2.0",
                    "method": method_name,
                    "params": params
                }
                self.validator.validate(notification)

    def test_all_event_payload_defs_have_validator_fixtures(self):
        """Every *Payload $def in event-payloads.schema.json has a fixture."""
        expected = set(_payload_def_names(self.schema))
        actual = {
            _method_to_payload_def(method)
            for method, _params in _REALM_NOTIFICATIONS.values()
        }
        self.assertEqual(
            actual,
            expected,
            "Payload $def coverage drifted.\n"
            f"  Missing fixtures: {sorted(expected - actual)}\n"
            f"  Extra fixtures:   {sorted(actual - expected)}",
        )
        self.assertEqual(len(expected), 50)

    def test_all_event_payload_fixtures_validate(self):
        """Each realm event fixture validates against its dedicated payload $def."""
        for prefix, (method, params) in _REALM_NOTIFICATIONS.items():
            def_name = _method_to_payload_def(method)
            with self.subTest(realm=prefix, payload_def=def_name):
                self.assertIn(def_name, self.schema["$defs"])
                _subschema_validator(self.schema, def_name).validate(params)

                notification = {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                }
                self.validator.validate(notification)

                realm = prefix.split("-", 1)[1]
                envelope = {
                    "event": method,
                    "realm": realm,
                    "timestamp": "2026-09-17T12:00:00Z",
                    "payload": params,
                }
                self.validator.validate(envelope)

    def test_incomplete_event_payload_fixtures_rejected(self):
        """Payload $defs reject objects missing required properties."""
        cases = [
            ("cadenceHabitHitPayload", {"habit_id": "meditation"}),
            ("triceTaskStateChangedPayload", {"task_id": "t1"}),
            ("quartermasterTxAppendedPayload", {"account": "Assets:Cash"}),
        ]
        for def_name, payload in cases:
            with self.subTest(payload_def=def_name):
                with self.assertRaises(jsonschema.ValidationError):
                    _subschema_validator(self.schema, def_name).validate(payload)

    def test_invalid_notification_payloads_rejected(self):
        """Malformed notification payloads fail validation."""
        invalid_samples = [
            # Notification MUST NOT contain 'id' member
            {"jsonrpc": "2.0", "id": 1, "method": "cadence:habitHit", "params": {"habit_id": "meditation", "date": "2026-09-17"}},
            # Missing method
            {"jsonrpc": "2.0", "params": {"habit_id": "meditation", "date": "2026-09-17"}},
            # Missing params
            {"jsonrpc": "2.0", "method": "cadence:habitHit"},
            # Invalid method pattern
            {"jsonrpc": "2.0", "method": "INVALID METHOD!", "params": {}},
            # Non-object params
            {"jsonrpc": "2.0", "method": "cadence:habitHit", "params": "not-an-object"},
        ]
        for idx, sample in enumerate(invalid_samples):
            with self.subTest(invalid_sample_idx=idx):
                with self.assertRaises(jsonschema.ValidationError):
                    self.validator.validate(sample)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRpcErrorEnvelopeSchema))
    suite.addTests(loader.loadTestsFromTestCase(TestRpcEventPayloadsSchema))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
