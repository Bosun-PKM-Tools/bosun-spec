"""tests/test_daemon_query_contracts.py

Pins the harbormaster runtime query schemas that live in bosun-spec as the
canonical daemon contracts (distinct $id from the full Graph DSL / federated
plan specifications).
"""

from __future__ import annotations

import json
import pathlib
import unittest

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCHEMAS = _REPO_ROOT / "schemas" / "v1" / "query"
_NEIGHBORHOOD = _SCHEMAS / "graph-neighborhood-query.schema.json"
_RUNTIME_PLAN = _SCHEMAS / "federated-query-plan.runtime.schema.json"
_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_ID_PREFIX = "https://bosunpkm.com/schemas/"

_CONTACT_URN = "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000"


def _load(path: pathlib.Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


class TestDaemonQueryContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.neighborhood = _load(_NEIGHBORHOOD)
        cls.runtime_plan = _load(_RUNTIME_PLAN)

    def test_neighborhood_pins_draft_and_canonical_id(self) -> None:
        self.assertEqual(self.neighborhood.get("$schema"), _DRAFT_2020_12)
        self.assertEqual(
            self.neighborhood.get("$id"),
            _ID_PREFIX + "v1/query/graph-neighborhood-query.schema.json",
        )
        self.assertEqual(self.neighborhood.get("required"), ["from"])
        self.assertEqual(self.neighborhood["properties"]["direction"]["enum"], ["out", "in", "both"])
        self.assertEqual(self.neighborhood["properties"]["depth"]["maximum"], 3)

    def test_runtime_plan_pins_draft_and_canonical_id(self) -> None:
        self.assertEqual(self.runtime_plan.get("$schema"), _DRAFT_2020_12)
        self.assertEqual(
            self.runtime_plan.get("$id"),
            _ID_PREFIX + "v1/query/federated-query-plan.runtime.schema.json",
        )
        self.assertEqual(self.runtime_plan.get("required"), ["sites", "queries"])

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_runtime_schemas_pass_meta_schema(self) -> None:
        for name, schema in (
            ("neighborhood", self.neighborhood),
            ("runtime_plan", self.runtime_plan),
        ):
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_harbormaster_neighborhood_query_validates(self) -> None:
        validator = Draft202012Validator(self.neighborhood)
        validator.validate({"from": _CONTACT_URN, "depth": 1, "direction": "out"})
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate({"from": _CONTACT_URN, "direction": "outbound"})

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_harbormaster_federated_plan_validates(self) -> None:
        validator = Draft202012Validator(self.runtime_plan)
        validator.validate(
            {
                "id": "live-join",
                "sites": [
                    {
                        "id": "alpha",
                        "command": ["python", "graph_query.py"],
                        "vault": "C:/vault-a",
                    }
                ],
                "queries": [
                    {
                        "id": "seed",
                        "site": "alpha",
                        "query": {"from": _CONTACT_URN, "depth": 1},
                    }
                ],
            }
        )
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(
                {
                    "plan_id": "not-a-runtime-plan",
                    "vault_endpoints": {},
                    "distributed_steps": [],
                    "join_keys": {},
                }
            )


if __name__ == "__main__":
    unittest.main()
