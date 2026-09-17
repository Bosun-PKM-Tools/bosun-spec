"""tests/test_graph_dsl_schema.py
────────────────────────────────
Unit test suite verifying:
  1. schemas/v1/query/graph-dsl.schema.json:
     - JSON Schema Draft 2020-12 strict compliance and meta-schema pass.
     - Canonical $id pinning: https://bosunpkm.com/schemas/v1/query/graph-dsl.schema.json.
  2. Query filter specification:
     - match_realm (single realm or realm list).
     - has_relation (predicate string, predicate list, or relationFilter object).
     - linked_from (single URN or URN array).
     - max_depth (integer >= 0).
     - predicate_pattern (regex pattern string).
  3. Directional traversal configuration:
     - direction: outbound, inbound, both, bidirectional.
     - edge_types: relations, wikilinks, stage_gates, all.
  4. Result projections:
     - nodes: vertex definition with id, realm, title, path, depth, attributes.
     - edges: directed connection with source, target, predicate, direction, edge_type.
     - subgraph_adjacency_matrix: square N x N matrix indexed by node URNs.
  5. Negative validation rejection of malformed queries and projections.
  6. End-to-end execution of graph queries against synthetic vault and schema validation of output.

Usage:
  python tests/test_graph_dsl_schema.py
  python -m pytest tests/test_graph_dsl_schema.py -v
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
    Node,
    Edge,
    VaultGraph,
    load_vault_graph,
)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "graph-dsl.schema.json"
_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID = "https://bosunpkm.com/schemas/v1/query/graph-dsl.schema.json"
_SYNTHETIC_VAULT_DIR = _REPO_ROOT / "fixtures" / "synthetic_vault"


class TestGraphDslSchema(unittest.TestCase):
    """Test suite validating Graph Query DSL schema and execution semantics."""

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
    # Schema Metadata and Draft 2020-12 Tests
    # -----------------------------------------------------------------------

    def test_schema_file_exists_and_parses_json(self):
        """Schema file exists and parses as valid JSON dictionary."""
        self.assertTrue(_SCHEMA_PATH.is_file())
        self.assertIsInstance(self.schema_json, dict)

    def test_schema_declares_draft_2020_12(self):
        """Schema must declare Draft 2020-12 meta-schema."""
        self.assertEqual(self.schema_json.get("$schema"), _DRAFT_2020_12)

    def test_schema_declares_canonical_id(self):
        """Schema must pin canonical $id."""
        self.assertEqual(self.schema_json.get("$id"), _CANONICAL_ID)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_schema_passes_meta_schema_check(self):
        """Schema must pass Draft202012Validator.check_schema()."""
        Draft202012Validator.check_schema(self.schema_json)

    # -----------------------------------------------------------------------
    # Query Filters Specification Tests
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_query_with_match_realm_filter(self):
        """Query with match_realm (single string and array) validates cleanly."""
        # Single string shortcut
        q1 = {
            "match_realm": "yeoman",
            "projections": ["nodes"],
        }
        self.validator.validate(q1)

        # Array of realms
        q2 = {
            "match_realm": ["careen", "trice", "charthouse"],
            "projections": ["nodes", "edges"],
        }
        self.validator.validate(q2)

        # In filters block
        q3 = {
            "filters": {
                "match_realm": ["yeoman", "qtm"],
            },
            "projections": ["nodes"],
        }
        self.validator.validate(q3)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_query_with_has_relation_filter(self):
        """Query with has_relation (string, list, and object) validates cleanly."""
        # Single predicate string
        q1 = {
            "has_relation": "assignedToContact",
            "projections": ["nodes", "edges"],
        }
        self.validator.validate(q1)

        # List of predicates
        q2 = {
            "has_relation": ["purchasedViaTx", "consultedProvider"],
            "projections": ["edges"],
        }
        self.validator.validate(q2)

        # Structured relation filter object
        q3 = {
            "has_relation": {
                "predicate": "campaign_lore_node",
                "target": "urn:charthouse:lore:018f3a00-0000-7000-8000-000000000048",
                "target_realm": "charthouse",
            },
            "projections": ["nodes", "edges"],
        }
        self.validator.validate(q3)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_query_with_linked_from_filter(self):
        """Query with linked_from root URN (single and array) validates cleanly."""
        q1 = {
            "linked_from": "urn:careen:project:018f3a00-0000-7000-8000-000000000009",
            "max_depth": 2,
            "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
        }
        self.validator.validate(q1)

        q2 = {
            "linked_from": [
                "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
            ],
            "max_depth": 3,
            "projections": ["nodes"],
        }
        self.validator.validate(q2)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_query_with_max_depth_filter(self):
        """Query with max_depth bounds (0, 1, 10) validates cleanly."""
        for depth in (0, 1, 5, 20):
            with self.subTest(depth=depth):
                q = {
                    "linked_from": "urn:bosun:root:018f3a00-0000-7000-8000-000000000001",
                    "max_depth": depth,
                    "projections": ["nodes"],
                }
                self.validator.validate(q)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_query_with_predicate_pattern_filter(self):
        """Query with predicate_pattern regex validates cleanly."""
        q = {
            "predicate_pattern": "^assignedTo.*",
            "projections": ["edges"],
        }
        self.validator.validate(q)

    # -----------------------------------------------------------------------
    # Directional Traversal and Edge Types Tests
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_query_directional_traversal(self):
        """All supported traversal directions validate cleanly."""
        for direction in ("outbound", "inbound", "both", "bidirectional"):
            with self.subTest(direction=direction):
                q = {
                    "linked_from": "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
                    "direction": direction,
                    "projections": ["nodes", "edges"],
                }
                self.validator.validate(q)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_query_edge_types(self):
        """All supported edge types validate cleanly."""
        for edge_types in (["relations"], ["wikilinks"], ["relations", "wikilinks"], ["all"]):
            with self.subTest(edge_types=edge_types):
                q = {
                    "edge_types": edge_types,
                    "projections": ["edges"],
                }
                self.validator.validate(q)

    # -----------------------------------------------------------------------
    # Result Projections Tests
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_result_projection_nodes(self):
        """Result with node projections conforms to graphQueryResult."""
        result = {
            "projections": ["nodes"],
            "nodes": [
                {
                    "id": "urn:careen:project:018f3a00-0000-7000-8000-000000000009",
                    "realm": "careen",
                    "title": "Quantum Routing Architecture",
                    "path": "09-careen/project-quantum-routing.md",
                    "depth": 0,
                    "attributes": {"kanban_stage": "in_progress"},
                },
                {
                    "id": "urn:charthouse:lore:018f3a00-0000-7000-8000-000000000048",
                    "realm": "charthouse",
                    "title": "Fleet Navigation Lore",
                    "path": "48-charthouse/lore-fleet-nav.md",
                    "depth": 1,
                },
            ],
            "metrics": {
                "node_count": 2,
                "traversal_depth": 1,
                "execution_time_ms": 1.25,
            },
        }
        self.validator.validate(result)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_result_projection_edges(self):
        """Result with edge projections conforms to graphQueryResult."""
        result = {
            "projections": ["edges"],
            "edges": [
                {
                    "source": "urn:careen:project:018f3a00-0000-7000-8000-000000000009",
                    "target": "urn:charthouse:lore:018f3a00-0000-7000-8000-000000000048",
                    "predicate": "campaign_lore_node",
                    "direction": "outbound",
                    "edge_type": "relation",
                    "weight": 1.0,
                },
                {
                    "source": "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                    "target": "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
                    "predicate": "assignedToContact",
                    "direction": "outbound",
                    "edge_type": "relation",
                    "weight": 1.0,
                },
            ],
            "metrics": {
                "edge_count": 2,
                "traversal_depth": 1,
            },
        }
        self.validator.validate(result)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_result_projection_subgraph_adjacency_matrix(self):
        """Result with subgraph_adjacency_matrix conforms to schema."""
        result = {
            "projections": ["subgraph_adjacency_matrix"],
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
        }
        self.validator.validate(result)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_unified_graph_query_envelope(self):
        """Unified graphQueryEnvelope containing both query and result passes validation."""
        envelope = {
            "query": {
                "query_id": "query-cross-realm-01",
                "linked_from": "urn:careen:project:018f3a00-0000-7000-8000-000000000009",
                "direction": "outbound",
                "max_depth": 2,
                "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
            },
            "result": {
                "query_id": "query-cross-realm-01",
                "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
                "nodes": [
                    {
                        "id": "urn:careen:project:018f3a00-0000-7000-8000-000000000009",
                        "realm": "careen",
                        "depth": 0,
                    }
                ],
                "edges": [],
                "subgraph_adjacency_matrix": {
                    "nodes": ["urn:careen:project:018f3a00-0000-7000-8000-000000000009"],
                    "matrix": [[0.0]],
                    "dimension": 1,
                    "directed": True,
                },
                "metrics": {
                    "node_count": 1,
                    "edge_count": 0,
                    "traversal_depth": 0,
                    "execution_time_ms": 0.5,
                },
            },
            "status": "success",
        }
        self.validator.validate(envelope)

    # -----------------------------------------------------------------------
    # Negative Validation Rejection Tests
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_invalid_urn_in_linked_from_rejected(self):
        """Malformed URN in linked_from must be rejected."""
        q = {
            "linked_from": "not-a-valid-urn",
            "projections": ["nodes"],
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(q)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_negative_max_depth_rejected(self):
        """Negative max_depth must be rejected."""
        q = {
            "max_depth": -1,
            "projections": ["nodes"],
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(q)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_invalid_direction_rejected(self):
        """Unrecognized traversal direction must be rejected."""
        q = {
            "direction": "perpendicular",
            "projections": ["nodes"],
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(q)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_invalid_projection_name_rejected(self):
        """Unrecognized projection identifier must be rejected."""
        q = {
            "projections": ["arbitrary_projection"],
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(q)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_missing_node_projection_required_fields_rejected(self):
        """Node projection missing id or realm must be rejected."""
        res = {
            "nodes": [
                {
                    "title": "Missing ID and Realm",
                }
            ]
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(res)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_missing_edge_projection_required_fields_rejected(self):
        """Edge projection missing source, target, predicate, direction, or edge_type rejected."""
        res = {
            "edges": [
                {
                    "source": "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002",
                    "target": "urn:trice:task:018f3a00-0000-7000-8000-000000000003",
                    # Missing predicate, direction, edge_type
                }
            ]
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(res)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_extra_properties_rejected_in_query(self):
        """Extraneous properties not declared in DSL must be rejected."""
        q = {
            "projections": ["nodes"],
            "sql_injection_payload": "SELECT * FROM users",
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(q)

    # -----------------------------------------------------------------------
    # End-to-End Vault Execution Tests
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
    def test_e2e_synthetic_vault_traversal_conforms_to_schema(self):
        """Execute queries against synthetic vault and ensure results validate."""
        if not _SYNTHETIC_VAULT_DIR.exists():
            self.skipTest(f"Synthetic vault not found at {_SYNTHETIC_VAULT_DIR}")

        vault_graph = load_vault_graph(_SYNTHETIC_VAULT_DIR)
        engine = GraphQueryEngine(vault_graph)

        # 1. Trice -> Yeoman contact query
        query1 = {
            "match_realm": "yeoman",
            "has_relation": "assignedToContact",
            "direction": "outbound",
            "max_depth": 2,
            "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
        }
        self.validator.validate(query1)
        res1 = engine.execute(query1)
        self.validator.validate(res1)
        self.assertIn("nodes", res1)
        self.assertIn("subgraph_adjacency_matrix", res1)

        # 2. Careen -> Charthouse lore node query
        query2 = {
            "match_realm": "charthouse",
            "has_relation": "campaign_lore_node",
            "direction": "both",
            "max_depth": 2,
            "projections": ["nodes", "edges"],
        }
        self.validator.validate(query2)
        res2 = engine.execute(query2)
        self.validator.validate(res2)

        # 3. Predicate pattern matching
        query3 = {
            "predicate_pattern": ".*Contact$",
            "direction": "outbound",
            "max_depth": 1,
            "projections": ["edges"],
        }
        self.validator.validate(query3)
        res3 = engine.execute(query3)
        self.validator.validate(res3)


if __name__ == "__main__":
    unittest.main()
