"""tests/test_advanced_graph_queries.py
─────────────────────────────────────
Advanced Graph Query DSL fixtures under
``tests/fixtures/queries/advanced/``:

  1. Load ``schemas/v1/query/graph-dsl.schema.json`` as Draft 2020-12.
  2. Valid multi-predicate fixtures MUST pass jsonschema validation:
     - ``careen-blocks-trice-assigned-contact.graph.json`` — Careen
       ``blocks`` a Trice task AND that task ``assignedToContact`` a
       Yeoman contact URN (ordered ``path`` AND of hops).
  3. Cypher/SPARQL siblings MUST exist, be non-empty, and mention the
     same predicates/URNs as the Graph DSL fixture.
  4. Invalid fixtures MUST raise ``ValidationError``:
     - ``invalid-illegal-predicate-in-path.graph.json`` — unknown verb
       (``appraisedBy``) combined with a valid stage-gate hop.

Usage
  python tests/test_advanced_graph_queries.py
  python -m pytest tests/test_advanced_graph_queries.py -v
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "graph-dsl.schema.json"
_ADVANCED_DIR = pathlib.Path(__file__).resolve().parent / "fixtures" / "queries" / "advanced"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_CANONICAL_ID = "https://bosunpkm.com/schemas/v1/query/graph-dsl.schema.json"

_VALID_STEM = "careen-blocks-trice-assigned-contact"
_VALID_GRAPH = f"{_VALID_STEM}.graph.json"
_VALID_CYPHER = f"{_VALID_STEM}.cypher"
_VALID_SPARQL = f"{_VALID_STEM}.sparql"
_INVALID_GRAPH = "invalid-illegal-predicate-in-path.graph.json"

_CAREEN_PROJECT = "urn:careen:project:018f3a00-0000-7000-8000-000000000009"
_TRICE_TASK = "urn:trice:task:018f3a00-0000-7000-8000-000000000003"
_YEOMAN_CONTACT = "urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002"


def _load_json(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _load_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _path_predicates(payload: dict) -> list[str]:
    hops = payload.get("path") or []
    return [str(hop["predicate"]) for hop in hops]


def _path_targets(payload: dict) -> list[str]:
    hops = payload.get("path") or []
    return [str(hop["target"]) for hop in hops if "target" in hop]


@unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema required")
class TestAdvancedGraphQueries(unittest.TestCase):
    """Validate advanced Graph DSL path fixtures and Cypher/SPARQL siblings."""

    @classmethod
    def setUpClass(cls):
        if not _SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Schema not found at {_SCHEMA_PATH}")
        cls.schema_json = _load_json(_SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema_json)
        cls.validator = Draft202012Validator(cls.schema_json)

    def test_schema_declares_draft_and_canonical_id(self):
        """Advanced fixtures validate against the pinned Graph DSL Draft 2020-12 schema."""
        self.assertEqual(self.schema_json.get("$schema"), _DRAFT_2020_12)
        self.assertEqual(self.schema_json.get("$id"), _CANONICAL_ID)

    def test_schema_declares_relation_path_and_combinator(self):
        """Schema must expose an ordered path AND of relationFilter hops."""
        defs = self.schema_json.get("$defs", {})
        self.assertIn("relationPath", defs)
        path_def = defs["relationPath"]
        self.assertEqual(path_def.get("minItems"), 2)
        graph_query = defs["graphQuery"]["properties"]
        self.assertIn("path", graph_query)
        query_filters = defs["queryFilters"]["properties"]
        self.assertIn("path", query_filters)

    def test_expected_advanced_fixtures_exist(self):
        """Catalogued advanced Graph DSL, Cypher, SPARQL, and invalid fixtures must be present."""
        self.assertTrue(_ADVANCED_DIR.is_dir(), f"Missing {_ADVANCED_DIR}")
        for name in (_VALID_GRAPH, _VALID_CYPHER, _VALID_SPARQL, _INVALID_GRAPH):
            with self.subTest(fixture=name):
                path = _ADVANCED_DIR / name
                self.assertTrue(path.is_file(), f"Missing fixture: {path}")

    def test_valid_multi_predicate_path_passes_draft_2020_12(self):
        """Careen→Trice→Yeoman path query must pass jsonschema validation."""
        payload = _load_json(_ADVANCED_DIR / _VALID_GRAPH)
        try:
            self.validator.validate(payload)
        except ValidationError as exc:
            self.fail(
                f"{_VALID_GRAPH} should be valid Graph DSL: {exc.message}\n"
                f"Failed path: {list(exc.path)}\n"
                f"Schema path: {list(exc.schema_path)}"
            )

    def test_valid_fixture_ands_blocks_and_assigned_to_contact(self):
        """Graph DSL must AND a stage-gate hop with assignedToContact to a Yeoman URN."""
        payload = _load_json(_ADVANCED_DIR / _VALID_GRAPH)
        self.assertEqual(payload["linked_from"], _CAREEN_PROJECT)
        self.assertGreaterEqual(payload["max_depth"], 2)
        self.assertIn("stage_gates", payload["edge_types"])
        self.assertEqual(set(payload["match_realm"]), {"careen", "trice", "yeoman"})

        predicates = _path_predicates(payload)
        self.assertGreaterEqual(len(predicates), 2)
        self.assertIn("blocks", predicates)
        self.assertIn("assignedToContact", predicates)

        hops_by_pred = {hop["predicate"]: hop for hop in payload["path"]}
        self.assertEqual(hops_by_pred["blocks"]["target"], _TRICE_TASK)
        self.assertEqual(
            hops_by_pred["assignedToContact"]["target"],
            _YEOMAN_CONTACT,
        )
        self.assertTrue(
            str(hops_by_pred["assignedToContact"]["target"]).startswith(
                "urn:yeoman:contact:"
            )
        )

    def test_cypher_and_sparql_equivalents_are_non_empty(self):
        """Cypher and SPARQL siblings must exist as non-empty documentation strings."""
        for name in (_VALID_CYPHER, _VALID_SPARQL):
            with self.subTest(fixture=name):
                text = _load_text(_ADVANCED_DIR / name).strip()
                self.assertTrue(text, f"{name} must be non-empty")

    def test_cypher_and_sparql_mention_dsl_predicates_and_urns(self):
        """Equivalent query strings must mention the same predicates and URNs as the DSL."""
        payload = _load_json(_ADVANCED_DIR / _VALID_GRAPH)
        predicates = _path_predicates(payload)
        targets = _path_targets(payload)
        linked_from = payload["linked_from"]
        if isinstance(linked_from, str):
            roots = [linked_from]
        else:
            roots = list(linked_from)

        for name in (_VALID_CYPHER, _VALID_SPARQL):
            with self.subTest(fixture=name):
                text = _load_text(_ADVANCED_DIR / name)
                for predicate in predicates:
                    self.assertIn(
                        predicate,
                        text,
                        f"{name} missing predicate {predicate!r}",
                    )
                for urn in roots + targets:
                    self.assertIn(urn, text, f"{name} missing URN {urn!r}")

    def test_invalid_illegal_predicate_in_path_fails_draft_2020_12(self):
        """Unknown verb combined with a valid hop must fail schema validation."""
        payload = _load_json(_ADVANCED_DIR / _INVALID_GRAPH)
        predicates = _path_predicates(payload)
        self.assertIn("blocks", predicates)
        self.assertIn("appraisedBy", predicates)
        with self.assertRaises(ValidationError):
            self.validator.validate(payload)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAdvancedGraphQueries)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
