"""tests/test_federated_query_schema.py
──────────────────────────────────────
Unit test suite verifying:
  1. schemas/v1/query/federated-query-plan.schema.json:
     - JSON Schema Draft 2020-12 strict compliance and meta-schema validation.
     - Canonical $id pinning: https://bosunpkm.com/schemas/v1/query/federated-query-plan.schema.json.
  2. Multi-vault endpoint declarations:
     - Local filesystem path endpoints (type=local/filesystem/path).
     - External subprocess stdio RPC endpoints (type=stdio_rpc/process/rpc/stdio).
     - String URI shorthand and remote HTTP endpoints.
  3. Ordered distributed traversal steps:
     - step_id, target_vault, operation, query payload.
     - Input dependencies (input_from_step, input_field).
     - Cross-vault joins (join_with_step, join_key, join_type).
     - Execution directives (parallel, optional, timeout_ms).
  4. Cross-vault URN join keys:
     - Dictionary and array representations.
     - Correlation strategies: exact_urn, uuid_v7, predicate_target, wikilink_slug, entity_id.
     - Cardinality constraints and field mappings.
  5. Aggregation directives and plan metadata:
     - merge_strategy (union, deduplicate, intersect), projections, global_limit.
     - Concurrency limits, max_total_duration_ms, semantic versioning.
  6. Negative validation:
     - Rejection of missing required properties, empty collections, invalid enums,
       unsupported endpoint types, malformed UUIDv7s, and illegal properties.
  7. End-to-end multi-vault federation plan payloads.

Usage:
  python tests/test_federated_query_schema.py
  python -m pytest tests/test_federated_query_schema.py -v
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

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "federated-query-plan.schema.json"
_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID = "https://bosunpkm.com/schemas/v1/query/federated-query-plan.schema.json"


class TestFederatedQuerySchema(unittest.TestCase):
    """Test suite validating Federated Graph Query Plan schema and cross-vault federation contracts."""

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
    # 1. Schema Metadata & Draft 2020-12 Meta-Schema Tests
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

    def test_schema_declares_exact_required_root_keys(self):
        """Root requires plan_id, vault_endpoints, distributed_steps, and join_keys."""
        required = set(self.schema_json.get("required", []))
        expected = {"plan_id", "vault_endpoints", "distributed_steps", "join_keys"}
        self.assertEqual(required, expected)

    def test_schema_disallows_additional_properties_at_root(self):
        """Root schema must enforce additionalProperties: false."""
        self.assertFalse(self.schema_json.get("additionalProperties", True))

    # -----------------------------------------------------------------------
    # Helper for Valid Base Plan
    # -----------------------------------------------------------------------

    def _make_valid_plan(self, **overrides) -> Dict[str, Any]:
        """Construct a minimal valid federated query plan payload."""
        base: Dict[str, Any] = {
            "plan_id": "018f2d5e-7a24-7330-9b48-18e0018a1a01",
            "title": "Cross-Vault Project & Contact Traversal",
            "description": "Federated query correlating Trice tasks in primary vault with Yeoman contacts in archive vault.",
            "version": "1.0.0",
            "vault_endpoints": {
                "vault_primary": {
                    "type": "local",
                    "path": "/vaults/primary",
                    "read_only": True,
                    "format": "markdown_pkm",
                },
                "vault_archive": {
                    "type": "stdio_rpc",
                    "command": "harbormaster",
                    "args": ["engine", "stdio", "--vault", "/vaults/archive"],
                    "env": {"BOSUN_LOG_LEVEL": "info"},
                    "timeout_ms": 8000,
                    "protocol": "jsonrpc-2.0",
                },
            },
            "distributed_steps": [
                {
                    "step_id": "step_fetch_tasks",
                    "target_vault": "vault_primary",
                    "operation": "traverse",
                    "query": {
                        "linked_from": "urn:bosun:trice:018f2d5e-7a24-7330-9b48-18e0018a1001",
                        "direction": "outbound",
                        "match_realm": "01_trice",
                        "projections": ["nodes", "edges"],
                    },
                },
                {
                    "step_id": "step_join_contacts",
                    "target_vault": "vault_archive",
                    "operation": "join",
                    "input_from_step": "step_fetch_tasks",
                    "input_field": "matched_nodes",
                    "join_with_step": "step_fetch_tasks",
                    "join_key": "task_assigned_contact",
                    "join_type": "inner",
                    "query": {
                        "match_realm": "03_yeoman",
                        "projections": ["nodes"],
                    },
                },
            ],
            "join_keys": {
                "task_assigned_contact": {
                    "key_id": "task_assigned_contact",
                    "source_field": "$pkm.relations.assignedToContact",
                    "target_field": "$pkm.id",
                    "matching_strategy": "exact_urn",
                    "cardinality": "many_to_one",
                    "description": "Matches task assignee URN with Yeoman contact identity URN.",
                }
            },
            "aggregation": {
                "merge_strategy": "deduplicate",
                "projections": ["nodes", "edges"],
                "global_limit": 500,
            },
            "max_total_duration_ms": 15000,
            "concurrency_limit": 2,
        }
        base.update(overrides)
        return base

    # -----------------------------------------------------------------------
    # 2. Vault Endpoints Specification Tests
    # -----------------------------------------------------------------------

    def test_valid_local_path_endpoint_variants(self):
        """Local path endpoints accept 'local', 'filesystem', and 'path' type discriminators."""
        for endpoint_type in ("local", "filesystem", "path"):
            plan = self._make_valid_plan(
                vault_endpoints={
                    "vault_local": {
                        "type": endpoint_type,
                        "path": "C:/vaults/research",
                        "alias": "vault_local",
                        "read_only": True,
                        "format": "sqlite",
                    }
                },
                distributed_steps=[
                    {
                        "step_id": "step_1",
                        "target_vault": "vault_local",
                        "operation": "scan",
                    }
                ],
            )
            self.validator.validate(plan)

    def test_valid_stdio_rpc_endpoint_variants(self):
        """Stdio RPC endpoints accept 'stdio_rpc', 'process', 'rpc', and 'stdio' types."""
        for endpoint_type in ("stdio_rpc", "process", "rpc", "stdio"):
            plan = self._make_valid_plan(
                vault_endpoints={
                    "vault_remote": {
                        "type": endpoint_type,
                        "command": "python",
                        "args": ["-m", "bosun.rpc_server"],
                        "working_dir": "/opt/bosun",
                        "env": {"VAULT_ID": "fleet_01"},
                        "timeout_ms": 5000,
                        "protocol": "jsonrpc-2.0",
                    }
                },
                distributed_steps=[
                    {
                        "step_id": "step_1",
                        "target_vault": "vault_remote",
                        "operation": "scan",
                    }
                ],
            )
            self.validator.validate(plan)

    def test_valid_uri_string_shorthand_endpoint(self):
        """Endpoints can be specified via simple string path or URI shorthand."""
        plan = self._make_valid_plan(
            vault_endpoints={
                "vault_fast": "/var/lib/bosun/vault",
                "vault_file_uri": "file:///C:/dev/vault",
            },
            distributed_steps=[
                {
                    "step_id": "step_1",
                    "target_vault": "vault_fast",
                    "operation": "scan",
                }
            ],
        )
        self.validator.validate(plan)

    def test_valid_http_endpoint(self):
        """Remote HTTP endpoints validate with url and auth_token."""
        plan = self._make_valid_plan(
            vault_endpoints={
                "vault_cloud": {
                    "type": "https",
                    "url": "https://vault.internal.network/query",
                    "timeout_ms": 12000,
                    "auth_token": "bearer-token-abc123xyz",
                }
            },
            distributed_steps=[
                {
                    "step_id": "step_1",
                    "target_vault": "vault_cloud",
                    "operation": "traverse",
                }
            ],
        )
        self.validator.validate(plan)

    def test_reject_empty_vault_endpoints(self):
        """vault_endpoints requires at least 1 endpoint."""
        plan = self._make_valid_plan(vault_endpoints={})
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_invalid_vault_endpoint_type(self):
        """Invalid endpoint discriminator must be rejected."""
        plan = self._make_valid_plan(
            vault_endpoints={
                "bad_vault": {
                    "type": "unsupported_protocol",
                    "path": "/data",
                }
            }
        )
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_local_endpoint_missing_path(self):
        """Local endpoint without required 'path' property is rejected."""
        plan = self._make_valid_plan(
            vault_endpoints={
                "vault_missing_path": {
                    "type": "local",
                }
            }
        )
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_stdio_endpoint_missing_command(self):
        """Stdio endpoint without required 'command' property is rejected."""
        plan = self._make_valid_plan(
            vault_endpoints={
                "vault_bad_stdio": {
                    "type": "stdio_rpc",
                    "args": ["run"],
                }
            }
        )
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    # -----------------------------------------------------------------------
    # 3. Distributed Traversal Steps Specification Tests
    # -----------------------------------------------------------------------

    def test_valid_step_operations(self):
        """All supported graph operations in distributed steps validate."""
        operations = [
            "traverse",
            "scan",
            "join",
            "project",
            "filter",
            "shortest_path",
            "subgraph",
            "aggregate",
        ]
        steps = [
            {
                "step_id": f"step_{idx}",
                "target_vault": "vault_primary",
                "operation": op,
            }
            for idx, op in enumerate(operations)
        ]
        plan = self._make_valid_plan(distributed_steps=steps)
        self.validator.validate(plan)

    def test_valid_integer_step_ids(self):
        """Step IDs can be integers as well as strings."""
        plan = self._make_valid_plan(
            distributed_steps=[
                {
                    "step_id": 1,
                    "target_vault": "vault_primary",
                    "operation": "scan",
                },
                {
                    "step_id": 2,
                    "target_vault": "vault_archive",
                    "operation": "join",
                    "input_from_step": 1,
                    "join_with_step": 1,
                    "join_key": "task_assigned_contact",
                },
            ]
        )
        self.validator.validate(plan)

    def test_valid_step_execution_flags(self):
        """Step parallel, optional, and timeout_ms execution directives validate."""
        plan = self._make_valid_plan(
            distributed_steps=[
                {
                    "step_id": "step_worker_a",
                    "target_vault": "vault_primary",
                    "operation": "scan",
                    "parallel": True,
                    "optional": False,
                    "timeout_ms": 3000,
                    "description": "Scan work tasks in parallel",
                },
                {
                    "step_id": "step_worker_b",
                    "target_vault": "vault_archive",
                    "operation": "scan",
                    "parallel": True,
                    "optional": True,
                    "timeout_ms": 4000,
                    "description": "Optional background scan on archive",
                },
            ]
        )
        self.validator.validate(plan)

    def test_valid_step_join_types(self):
        """Cross-vault join types (inner, left_outer, cross, semi, anti) validate."""
        for join_type in ("inner", "left_outer", "cross", "semi", "anti"):
            plan = self._make_valid_plan(
                distributed_steps=[
                    {
                        "step_id": "step_base",
                        "target_vault": "vault_primary",
                        "operation": "scan",
                    },
                    {
                        "step_id": "step_join",
                        "target_vault": "vault_archive",
                        "operation": "join",
                        "input_from_step": "step_base",
                        "join_with_step": "step_base",
                        "join_key": "task_assigned_contact",
                        "join_type": join_type,
                    },
                ]
            )
            self.validator.validate(plan)

    def test_reject_empty_distributed_steps(self):
        """distributed_steps requires minItems: 1."""
        plan = self._make_valid_plan(distributed_steps=[])
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_step_missing_required_fields(self):
        """Step missing target_vault or operation is rejected."""
        missing_target = {
            "step_id": "s1",
            "operation": "traverse",
        }
        plan = self._make_valid_plan(distributed_steps=[missing_target])
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

        missing_op = {
            "step_id": "s1",
            "target_vault": "vault_primary",
        }
        plan = self._make_valid_plan(distributed_steps=[missing_op])
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_invalid_step_operation(self):
        """Step operation not in enum is rejected."""
        bad_step = {
            "step_id": "s1",
            "target_vault": "vault_primary",
            "operation": "delete_everything",
        }
        plan = self._make_valid_plan(distributed_steps=[bad_step])
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_negative_step_timeout(self):
        """timeout_ms in step cannot be negative."""
        bad_step = {
            "step_id": "s1",
            "target_vault": "vault_primary",
            "operation": "traverse",
            "timeout_ms": -500,
        }
        plan = self._make_valid_plan(distributed_steps=[bad_step])
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    # -----------------------------------------------------------------------
    # 4. Cross-Vault Join Keys Specification Tests
    # -----------------------------------------------------------------------

    def test_valid_join_keys_array_format(self):
        """join_keys accepts array format as well as dictionary format."""
        plan = self._make_valid_plan(
            join_keys=[
                {
                    "key_id": "gear_to_tx",
                    "source_field": "$pkm.relations.purchasedViaTx",
                    "target_field": "$pkm.id",
                    "matching_strategy": "exact_urn",
                    "cardinality": "many_to_one",
                },
                {
                    "key_id": "project_to_lore",
                    "source_field": "campaign_lore_node",
                    "target_field": "lore_id",
                    "matching_strategy": "uuid_v7",
                    "cardinality": "one_to_one",
                },
            ]
        )
        self.validator.validate(plan)

    def test_valid_matching_strategies(self):
        """All supported matching strategies validate."""
        strategies = [
            "exact_urn",
            "uuid_v7",
            "predicate_target",
            "wikilink_slug",
            "entity_id",
        ]
        for strategy in strategies:
            plan = self._make_valid_plan(
                join_keys={
                    f"key_{strategy}": {
                        "source_field": "source",
                        "target_field": "target",
                        "matching_strategy": strategy,
                    }
                }
            )
            self.validator.validate(plan)

    def test_valid_cardinalities(self):
        """All supported cardinality enums validate."""
        cardinalities = ["one_to_one", "one_to_many", "many_to_many", "many_to_one"]
        for card in cardinalities:
            plan = self._make_valid_plan(
                join_keys={
                    "test_key": {
                        "source_field": "source",
                        "target_field": "target",
                        "matching_strategy": "exact_urn",
                        "cardinality": card,
                    }
                }
            )
            self.validator.validate(plan)

    def test_reject_join_key_missing_required_fields(self):
        """Join key definition must contain source_field, target_field, and matching_strategy."""
        missing_target = {
            "test_key": {
                "source_field": "source",
                "matching_strategy": "exact_urn",
            }
        }
        plan = self._make_valid_plan(join_keys=missing_target)
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

        missing_strategy = {
            "test_key": {
                "source_field": "source",
                "target_field": "target",
            }
        }
        plan = self._make_valid_plan(join_keys=missing_strategy)
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_invalid_matching_strategy(self):
        """Unsupported matching strategy is rejected."""
        bad_strategy = {
            "test_key": {
                "source_field": "source",
                "target_field": "target",
                "matching_strategy": "levenshtein_distance_fuzzy",
            }
        }
        plan = self._make_valid_plan(join_keys=bad_strategy)
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_empty_join_keys(self):
        """Empty join_keys map or list is rejected."""
        plan_empty_map = self._make_valid_plan(join_keys={})
        with self.assertRaises(ValidationError):
            self.validator.validate(plan_empty_map)

        plan_empty_list = self._make_valid_plan(join_keys=[])
        with self.assertRaises(ValidationError):
            self.validator.validate(plan_empty_list)

    # -----------------------------------------------------------------------
    # 5. Plan-Level Aggregation & Configuration Tests
    # -----------------------------------------------------------------------

    def test_valid_aggregation_merge_strategies(self):
        """union, deduplicate, intersect merge strategies validate."""
        for strategy in ("union", "deduplicate", "intersect"):
            plan = self._make_valid_plan(
                aggregation={
                    "merge_strategy": strategy,
                    "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
                    "global_limit": 100,
                }
            )
            self.validator.validate(plan)

    def test_reject_invalid_aggregation_merge_strategy(self):
        """Unsupported merge strategy is rejected."""
        plan = self._make_valid_plan(
            aggregation={
                "merge_strategy": "fuzzy_coalesce",
            }
        )
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_valid_urn_plan_id(self):
        """plan_id can be formatted as urn:uuid:... as well as naked UUIDv7."""
        plan = self._make_valid_plan(
            plan_id="urn:uuid:018f2d5e-7a24-7330-9b48-18e0018a1a01"
        )
        self.validator.validate(plan)

    def test_reject_malformed_plan_id(self):
        """Malformed plan_id not conforming to UUIDv7 pattern is rejected."""
        plan = self._make_valid_plan(plan_id="not-a-valid-uuidv7")
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_malformed_semantic_version(self):
        """Version must follow X.Y.Z semver pattern."""
        plan = self._make_valid_plan(version="v1.0-alpha")
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_negative_concurrency_limit(self):
        """concurrency_limit must be >= 1."""
        plan = self._make_valid_plan(concurrency_limit=0)
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    def test_reject_extraneous_root_properties(self):
        """additionalProperties: false rejects unknown top-level keys."""
        plan = self._make_valid_plan(unknown_extension_field={"data": 123})
        with self.assertRaises(ValidationError):
            self.validator.validate(plan)

    # -----------------------------------------------------------------------
    # 6. Realistic Multi-Vault Cross-Realm Federation Scenarios
    # -----------------------------------------------------------------------

    def test_three_vault_cross_realm_federated_pipeline(self):
        """Validates a realistic 3-vault pipeline correlating Tasks -> Gear -> Financial Tx."""
        pipeline_plan = {
            "plan_id": "018f2d5e-7a24-7330-9b48-18e0018a2001",
            "title": "Operation Expedited Re-supply: Trice -> Supercargo -> Quartermaster",
            "description": "Multi-vault traversal resolving task gear requirements and verifying Quartermaster financial settlement across work and fleet vaults.",
            "version": "1.1.0",
            "vault_endpoints": {
                "vault_work": {
                    "type": "filesystem",
                    "path": "/vaults/work_active",
                    "read_only": True,
                    "format": "markdown_pkm",
                },
                "vault_fleet_ops": {
                    "type": "stdio_rpc",
                    "command": "bosun-vault-rpc",
                    "args": ["--socket-stdio", "--vault", "/vaults/fleet_ops"],
                    "env": {"RUST_LOG": "warn"},
                    "timeout_ms": 6000,
                    "protocol": "jsonrpc-2.0",
                },
                "vault_finance": {
                    "type": "https",
                    "url": "https://finance-vault.bosun.internal/v1/rpc",
                    "timeout_ms": 10000,
                    "auth_token": "vault-jwt-token",
                },
            },
            "distributed_steps": [
                {
                    "step_id": "step_1_extract_tasks",
                    "target_vault": "vault_work",
                    "operation": "traverse",
                    "query": {
                        "linked_from": "urn:bosun:trice:018f2d5e-7a24-7330-9b48-18e0018a1001",
                        "match_realm": "01_trice",
                        "direction": "outbound",
                        "edge_types": ["relations"],
                        "projections": ["nodes", "edges"],
                    },
                },
                {
                    "step_id": "step_2_resolve_gear",
                    "target_vault": "vault_fleet_ops",
                    "operation": "join",
                    "input_from_step": "step_1_extract_tasks",
                    "input_field": "matched_nodes",
                    "join_with_step": "step_1_extract_tasks",
                    "join_key": "task_to_gear",
                    "join_type": "inner",
                    "query": {
                        "match_realm": "04_supercargo",
                        "projections": ["nodes", "edges"],
                    },
                },
                {
                    "step_id": "step_3_audit_transactions",
                    "target_vault": "vault_finance",
                    "operation": "join",
                    "input_from_step": "step_2_resolve_gear",
                    "input_field": "matched_nodes",
                    "join_with_step": "step_2_resolve_gear",
                    "join_key": "gear_to_tx",
                    "join_type": "left_outer",
                    "optional": True,
                    "query": {
                        "match_realm": "05_quartermaster",
                        "projections": ["nodes"],
                    },
                },
            ],
            "join_keys": {
                "task_to_gear": {
                    "key_id": "task_to_gear",
                    "source_field": "$pkm.relations.requiredGear",
                    "target_field": "$pkm.id",
                    "matching_strategy": "exact_urn",
                    "cardinality": "one_to_many",
                },
                "gear_to_tx": {
                    "key_id": "gear_to_tx",
                    "source_field": "$pkm.relations.purchasedViaTx",
                    "target_field": "$pkm.id",
                    "matching_strategy": "exact_urn",
                    "cardinality": "many_to_one",
                },
            },
            "aggregation": {
                "merge_strategy": "deduplicate",
                "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
                "global_limit": 1000,
            },
            "max_total_duration_ms": 25000,
            "concurrency_limit": 3,
        }
        self.validator.validate(pipeline_plan)


if __name__ == "__main__":
    unittest.main()
