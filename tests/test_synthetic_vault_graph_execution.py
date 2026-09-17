"""tests/test_synthetic_vault_graph_execution.py
────────────────────────────────────────────
Ground-truth Graph DSL execution against ``fixtures/synthetic_vault/``.

Pinned from the golden vault notes (not invented URNs):

  Single-hop
    ``03-trice/task-archive-ingest.md``
      ``assignedToContact`` → Ada Lovelace
  Multi-hop path AND (Careen → Trice → Yeoman)
    ``09-careen/project-worldbuilding-refit.md``
      ``actionItemDerivedFrom`` → ``03-trice/task-campaign-worldbuilding.md``
      ``assignedToContact`` → ``02-yeoman/contact-grace-hopper.md``
  Empty / no-match
    the same Careen project has no ``blocked_by`` hop, so a
    ``blocked_by`` then ``assignedToContact`` path matches nothing.

Uses ``scripts.graph_query.GraphQueryEngine`` (realm-typed aliases and
``path`` AND hops from ``lint_relations_graph``). Assertions compare
sorted URN and path sets.

Usage
  python tests/test_synthetic_vault_graph_execution.py
  python -m pytest tests/test_synthetic_vault_graph_execution.py -v
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.graph_query import GraphQueryEngine, load_vault_graph

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_GOLDEN_VAULT = _REPO_ROOT / "fixtures" / "synthetic_vault"
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "graph-dsl.schema.json"

# Canonical $pkm.id values and realm-typed aliases, read from the notes.
_CAREEN_WORLDBUILDING_UUID = "01a0aecf-0d00-7e68-b8fb-5086ff903c61"
_TRICE_CAMPAIGN_UUID = "01a0aecf-0d00-7faf-bc3f-9a51a93c7c05"
_YEOMAN_HOPPER_UUID = "01a0aecf-0d00-756e-bea1-b47c88baac88"
_TRICE_ARCHIVE_UUID = "01a0aecf-0d00-769b-ad98-25fb517ad453"
_YEOMAN_ADA_UUID = "01a0aecf-0d00-77a6-af0b-d05448582ebb"

_CAREEN_WORLDBUILDING_ID = f"urn:uuid:{_CAREEN_WORLDBUILDING_UUID}"
_CAREEN_WORLDBUILDING_PROJECT = f"urn:careen:project:{_CAREEN_WORLDBUILDING_UUID}"
_TRICE_CAMPAIGN_ID = f"urn:uuid:{_TRICE_CAMPAIGN_UUID}"
_TRICE_CAMPAIGN_TASK = f"urn:trice:task:{_TRICE_CAMPAIGN_UUID}"
_YEOMAN_HOPPER_ID = f"urn:uuid:{_YEOMAN_HOPPER_UUID}"
_YEOMAN_HOPPER_CONTACT = f"urn:yeoman:contact:{_YEOMAN_HOPPER_UUID}"
_TRICE_ARCHIVE_ID = f"urn:uuid:{_TRICE_ARCHIVE_UUID}"
_TRICE_ARCHIVE_TASK = f"urn:trice:task:{_TRICE_ARCHIVE_UUID}"
_YEOMAN_ADA_ID = f"urn:uuid:{_YEOMAN_ADA_UUID}"
_YEOMAN_ADA_CONTACT = f"urn:yeoman:contact:{_YEOMAN_ADA_UUID}"

_PATH_CAREEN_WORLDBUILDING = "09-careen/project-worldbuilding-refit.md"
_PATH_TRICE_CAMPAIGN = "03-trice/task-campaign-worldbuilding.md"
_PATH_YEOMAN_HOPPER = "02-yeoman/contact-grace-hopper.md"
_PATH_TRICE_ARCHIVE = "03-trice/task-archive-ingest.md"
_PATH_YEOMAN_ADA = "02-yeoman/contact-ada-lovelace.md"

_SINGLE_HOP_URNS = [_TRICE_ARCHIVE_ID, _YEOMAN_ADA_ID]
_SINGLE_HOP_PATHS = [_PATH_TRICE_ARCHIVE, _PATH_YEOMAN_ADA]
_MULTI_HOP_URNS = [
    _CAREEN_WORLDBUILDING_ID,
    _TRICE_CAMPAIGN_ID,
    _YEOMAN_HOPPER_ID,
]
_MULTI_HOP_PATHS = [
    _PATH_CAREEN_WORLDBUILDING,
    _PATH_TRICE_CAMPAIGN,
    _PATH_YEOMAN_HOPPER,
]


def _sorted_ids(result: dict) -> list[str]:
    return sorted(str(node["id"]) for node in result.get("nodes", []))


def _sorted_paths(result: dict) -> list[str]:
    return sorted(
        str(node["path"])
        for node in result.get("nodes", [])
        if node.get("path")
    )


class TestSyntheticVaultGraphExecution(unittest.TestCase):
    """Execute Graph DSL queries against the golden 200-note vault."""

    @classmethod
    def setUpClass(cls):
        if not _GOLDEN_VAULT.is_dir():
            raise FileNotFoundError(f"missing golden vault: {_GOLDEN_VAULT}")
        cls.graph = load_vault_graph(_GOLDEN_VAULT)
        cls.engine = GraphQueryEngine(cls.graph)
        cls.validator = None
        if _HAS_JSONSCHEMA and _SCHEMA_PATH.is_file():
            import json

            with open(_SCHEMA_PATH, encoding="utf-8") as handle:
                schema = json.load(handle)
            Draft202012Validator.check_schema(schema)
            cls.validator = Draft202012Validator(schema)

    def _execute(self, query: dict) -> dict:
        if self.validator is not None:
            try:
                self.validator.validate(query)
            except ValidationError as exc:
                self.fail(
                    f"query must remain Draft 2020-12 valid: {exc.message}\n"
                    f"Failed path: {list(exc.path)}"
                )
        result = self.engine.execute(query)
        self.assertIn("nodes", result)
        return result

    def test_vault_still_wires_careen_trice_yeoman_chain(self):
        """Ground-truth edges must still exist on the indexed vault graph."""
        self.assertGreaterEqual(len(self.graph.nodes), 200)

        careen = self.graph.resolve_urn(_CAREEN_WORLDBUILDING_PROJECT)
        self.assertEqual(careen, _CAREEN_WORLDBUILDING_ID)
        trice_campaign = self.graph.resolve_urn(_TRICE_CAMPAIGN_TASK)
        self.assertEqual(trice_campaign, _TRICE_CAMPAIGN_ID)
        hopper = self.graph.resolve_urn(_YEOMAN_HOPPER_CONTACT)
        self.assertEqual(hopper, _YEOMAN_HOPPER_ID)
        trice_archive = self.graph.resolve_urn(_TRICE_ARCHIVE_TASK)
        self.assertEqual(trice_archive, _TRICE_ARCHIVE_ID)
        ada = self.graph.resolve_urn(_YEOMAN_ADA_CONTACT)
        self.assertEqual(ada, _YEOMAN_ADA_ID)

        careen_edges = {
            (edge.predicate, self.graph.resolve_urn(edge.target))
            for edge in self.graph.out_edges.get(careen, [])
        }
        self.assertIn(
            ("actionItemDerivedFrom", _TRICE_CAMPAIGN_ID),
            careen_edges,
        )

        campaign_edges = {
            (edge.predicate, self.graph.resolve_urn(edge.target))
            for edge in self.graph.out_edges.get(trice_campaign, [])
        }
        self.assertIn(("assignedToContact", _YEOMAN_HOPPER_ID), campaign_edges)

        archive_edges = {
            (edge.predicate, self.graph.resolve_urn(edge.target))
            for edge in self.graph.out_edges.get(trice_archive, [])
        }
        self.assertIn(("assignedToContact", _YEOMAN_ADA_ID), archive_edges)

    def test_single_hop_archive_ingest_assigned_to_ada(self):
        """Trice archive-ingest → assignedToContact → Yeoman Ada Lovelace."""
        query = {
            "query_id": "synthetic-single-hop-archive-ada",
            "linked_from": _TRICE_ARCHIVE_TASK,
            "direction": "outbound",
            "edge_types": ["relations"],
            "max_depth": 1,
            "has_relation": {
                "predicate": "assignedToContact",
                "target": _YEOMAN_ADA_CONTACT,
                "target_realm": "yeoman",
            },
            "filters": {
                "include_wikilinks": False,
                "include_relations": True,
                "max_depth": 1,
            },
            "projections": ["nodes", "edges"],
        }
        result = self._execute(query)
        self.assertEqual(_sorted_ids(result), sorted(_SINGLE_HOP_URNS))
        self.assertEqual(_sorted_paths(result), sorted(_SINGLE_HOP_PATHS))
        self.assertEqual(len(result["nodes"]), 2)

    def test_multihop_careen_trice_yeoman_path_and(self):
        """Careen worldbuilding → Trice campaign task → Yeoman Hopper."""
        query = {
            "query_id": "synthetic-multihop-careen-trice-yeoman",
            "linked_from": _CAREEN_WORLDBUILDING_PROJECT,
            "direction": "outbound",
            "edge_types": ["relations", "stage_gates"],
            "max_depth": 2,
            "match_realm": ["careen", "trice", "yeoman"],
            "path": [
                {
                    "predicate": "actionItemDerivedFrom",
                    "target": _TRICE_CAMPAIGN_TASK,
                    "target_realm": "trice",
                },
                {
                    "predicate": "assignedToContact",
                    "target": _YEOMAN_HOPPER_CONTACT,
                    "target_realm": "yeoman",
                },
            ],
            "filters": {
                "include_wikilinks": False,
                "include_relations": True,
                "max_depth": 2,
            },
            "projections": ["nodes", "edges"],
        }
        result = self._execute(query)
        self.assertEqual(_sorted_ids(result), sorted(_MULTI_HOP_URNS))
        self.assertEqual(_sorted_paths(result), sorted(_MULTI_HOP_PATHS))
        self.assertEqual(len(result["nodes"]), 3)
        # Path AND must exclude the project's campaign_lore_node Charthouse hop.
        lore_paths = [
            node["path"]
            for node in result["nodes"]
            if str(node.get("path", "")).startswith("48-charthouse/")
        ]
        self.assertEqual(lore_paths, [])

    def test_blocked_by_path_has_no_match(self):
        """Careen worldbuilding has no blocked_by hop, so the path is empty."""
        query = {
            "query_id": "synthetic-empty-blocked-by-path",
            "linked_from": _CAREEN_WORLDBUILDING_PROJECT,
            "direction": "outbound",
            "edge_types": ["relations", "stage_gates"],
            "max_depth": 2,
            "path": [
                {"predicate": "blocked_by", "target_realm": "trice"},
                {
                    "predicate": "assignedToContact",
                    "target_realm": "yeoman",
                },
            ],
            "filters": {
                "include_wikilinks": False,
                "include_relations": True,
                "max_depth": 2,
            },
            "projections": ["nodes", "edges"],
        }
        result = self._execute(query)
        self.assertEqual(_sorted_ids(result), [])
        self.assertEqual(_sorted_paths(result), [])
        self.assertEqual(result.get("nodes"), [])


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSyntheticVaultGraphExecution)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
