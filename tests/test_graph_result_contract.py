"""tests/test_graph_result_contract.py
───────────────────────────────────
Contract validator and test suite for Graph Query Execution Output.

Invariants Verified:
  1. JSON Schema Draft 2020-12 strict enforcement for schemas/v1/query/graph-result.schema.json.
  2. Canonical $id matches https://bosunpkm.com/schemas/v1/query/graph-result.schema.json.
  3. Enforces root structure:
     {"query_id": <uuidv7>, "matched_nodes": [...], "resolved_edges": [...], "depth_reached": <int>, "execution_duration_ms": <float>}.
  4. Formalizes result payloads for Graph DSL queries (nodes, resolved edges, and adjacency matrices).
  5. Rejects malformed IDs, missing required fields, negative values, and illegal properties.
  6. Live validation of GraphQueryEngine.execute_result_contract() against synthetic vault data.

Usage:
  python tests/test_graph_result_contract.py
  python -m pytest tests/test_graph_result_contract.py -v
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest
from typing import Any, Dict

# Ensure repo root is on sys.path
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.graph_query import (
    GraphQueryEngine,
    load_vault_graph,
)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "graph-result.schema.json"
_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID = "https://bosunpkm.com/schemas/v1/query/graph-result.schema.json"
_SYNTHETIC_VAULT_DIR = _REPO_ROOT / "fixtures" / "synthetic_vault"


class TestGraphResultContract(unittest.TestCase):
    """Validation test suite for Graph Query Execution Result schema and contract."""

    @classmethod
    def setUpClass(cls):
        if not _SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Schema not found at {_SCHEMA_PATH}")
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            cls.schema_json = json.load(fh)
        if _HAS_JSONSCHEMA:
            Draft202012Validator.check_schema(cls.schema_json)
            cls.validator = Draft202012Validator(cls.schema_json)

    # -----------------------------------------------------------------------
    # Schema Metadata and Draft 2020-12 Verification
    # -----------------------------------------------------------------------

    def test_schema_file_exists_and_parses_json(self):
        """Schema file exists and parses as valid JSON dictionary."""
        self.assertTrue(_SCHEMA_PATH.is_file())
        self.assertIsInstance(self.schema_json, dict)

    def test_schema_declares_draft_2020_12(self):
        """Schema must declare Draft 2020-12 meta-schema."""
        self.assertEqual(self.schema_json.get("$schema"), _DRAFT_2020_12)

    def test_schema_declares_canonical_id(self):
        """Schema must pin canonical $id matching filesystem relative path."""
        self.assertEqual(self.schema_json.get("$id"), _CANONICAL_ID)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_schema_passes_meta_schema_check(self):
        """Schema itself must pass Draft202012Validator.check_schema()."""
        Draft202012Validator.check_schema(self.schema_json)

    def test_schema_declares_exact_required_root_keys(self):
        """Schema specifies the 5 mandatory contract keys."""
        required = set(self.schema_json.get("required", []))
        expected = {
            "query_id",
            "matched_nodes",
            "resolved_edges",
            "depth_reached",
            "execution_duration_ms",
        }
        self.assertEqual(required, expected)

    # -----------------------------------------------------------------------
    # Positive Validation Tests (Canonical Result Payloads)
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_valid_minimal_result_payload(self):
        """Minimal result payload containing the 5 required fields validates."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [],
            "depth_reached": 0,
            "execution_duration_ms": 0.45,
        }
        self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_valid_result_with_urn_query_id(self):
        """query_id formatted as urn:uuid:<uuidv7> validates."""
        payload = {
            "query_id": "urn:uuid:018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [
                {
                    "id": "urn:careen:project:018f3a00-0000-7000-8000-000000000009",
                    "realm": "careen",
                    "title": "Quantum Routing Architecture",
                    "path": "09-careen/project-quantum-routing.md",
                    "depth": 0,
                }
            ],
            "resolved_edges": [],
            "depth_reached": 0,
            "execution_duration_ms": 1.12,
        }
        self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_valid_full_result_with_nodes_edges_and_matrix(self):
        """Full execution payload with nodes, resolved edges, and adjacency matrix."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000042",
            "matched_nodes": [
                {
                    "id": "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                    "realm": "trice",
                    "title": "Provision Yeoman Integration",
                    "path": "03-trice/task-provision.md",
                    "depth": 0,
                    "attributes": {"task_state": "done", "priority": "high"},
                },
                {
                    "id": "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
                    "realm": "yeoman",
                    "title": "Chief Engineer",
                    "path": "02-yeoman/contact-chief.md",
                    "depth": 1,
                },
            ],
            "resolved_edges": [
                {
                    "source": "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                    "target": "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
                    "predicate": "assignedToContact",
                    "direction": "outbound",
                    "edge_type": "relation",
                    "weight": 1.0,
                    "properties": {"provenance": "frontmatter"},
                }
            ],
            "subgraph_adjacency_matrix": {
                "nodes": [
                    "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                    "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
                ],
                "matrix": [
                    [0.0, 1.0],
                    [0.0, 0.0],
                ],
                "dimension": 2,
                "directed": True,
            },
            "shortest_path": [
                "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
            ],
            "depth_reached": 1,
            "execution_duration_ms": 2.45,
            "status": "success",
            "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
            "metrics": {
                "node_count": 2,
                "edge_count": 1,
                "traversal_depth": 1,
                "execution_time_ms": 2.45,
            },
        }
        self.validator.validate(payload)

    # -----------------------------------------------------------------------
    # Negative Validation Tests (Rejection of Non-Conforming Shapes)
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_missing_query_id(self):
        """Payload missing query_id must be rejected."""
        payload = {
            "matched_nodes": [],
            "resolved_edges": [],
            "depth_reached": 0,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_malformed_query_id(self):
        """Payload with non-UUID query_id must be rejected."""
        payload = {
            "query_id": "not-a-valid-uuid-v7",
            "matched_nodes": [],
            "resolved_edges": [],
            "depth_reached": 0,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_missing_matched_nodes(self):
        """Payload missing matched_nodes must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "resolved_edges": [],
            "depth_reached": 0,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_malformed_matched_node_missing_id_or_realm(self):
        """Node in matched_nodes missing required 'id' or 'realm' must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [
                {
                    "title": "Node Missing ID and Realm",
                }
            ],
            "resolved_edges": [],
            "depth_reached": 0,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_missing_resolved_edges(self):
        """Payload missing resolved_edges must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "depth_reached": 0,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_malformed_resolved_edge_missing_fields(self):
        """Edge missing source, target, predicate, direction, or edge_type must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [
                {
                    "source": "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                    "target": "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
                    # Missing predicate, direction, edge_type
                }
            ],
            "depth_reached": 1,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_invalid_edge_direction(self):
        """Edge with illegal direction (e.g. 'perpendicular') must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [
                {
                    "source": "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                    "target": "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
                    "predicate": "assignedToContact",
                    "direction": "perpendicular",
                    "edge_type": "relation",
                }
            ],
            "depth_reached": 1,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_missing_depth_reached(self):
        """Payload missing depth_reached must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [],
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_negative_depth_reached(self):
        """Negative depth_reached must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [],
            "depth_reached": -1,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_float_depth_reached(self):
        """Floating point depth_reached must be rejected (must be integer)."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [],
            "depth_reached": 2.5,
            "execution_duration_ms": 1.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_missing_execution_duration_ms(self):
        """Payload missing execution_duration_ms must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [],
            "depth_reached": 0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_negative_execution_duration_ms(self):
        """Negative execution_duration_ms must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [],
            "depth_reached": 0,
            "execution_duration_ms": -5.0,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_reject_extra_unknown_fields(self):
        """Extraneous attributes not defined in contract must be rejected."""
        payload = {
            "query_id": "018f3a00-0000-7000-8000-000000000001",
            "matched_nodes": [],
            "resolved_edges": [],
            "depth_reached": 0,
            "execution_duration_ms": 1.0,
            "unexpected_injected_field": "disallowed",
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)

    # -----------------------------------------------------------------------
    # Live Engine Execution Contract Verification
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_live_engine_execute_result_contract_synthetic_vault(self):
        """Execute query on synthetic vault and verify result conforms strictly to contract."""
        if not _SYNTHETIC_VAULT_DIR.exists():
            self.skipTest(f"Synthetic vault not found at {_SYNTHETIC_VAULT_DIR}")

        vault_graph = load_vault_graph(_SYNTHETIC_VAULT_DIR)
        engine = GraphQueryEngine(vault_graph)

        query = {
            "match_realm": "yeoman",
            "has_relation": "assignedToContact",
            "direction": "outbound",
            "max_depth": 2,
            "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
        }
        fixed_query_id = "018f3a00-0000-7000-8000-000000000099"
        result_payload = engine.execute_result_contract(query, query_id=fixed_query_id)

        # Validate against graph-result.schema.json
        self.validator.validate(result_payload)

        # Assert mandatory contract keys
        self.assertEqual(result_payload["query_id"], fixed_query_id)
        self.assertIsInstance(result_payload["matched_nodes"], list)
        self.assertIsInstance(result_payload["resolved_edges"], list)
        self.assertIsInstance(result_payload["depth_reached"], int)
        self.assertIsInstance(result_payload["execution_duration_ms"], (int, float))
        self.assertGreaterEqual(result_payload["depth_reached"], 0)
        self.assertGreaterEqual(result_payload["execution_duration_ms"], 0.0)

        # If adjacency matrix was requested, assert it is present and valid
        self.assertIn("subgraph_adjacency_matrix", result_payload)
        matrix_obj = result_payload["subgraph_adjacency_matrix"]
        self.assertIn("nodes", matrix_obj)
        self.assertIn("matrix", matrix_obj)


if __name__ == "__main__":
    unittest.main()
