"""
tests/test_relations_spec.py
────────────────────────────
Validates the typed `$pkm.relations` contract and the JSON-RPC 2.0 fleet
method matrix:

  1. ``schemas/v1/relations/relations.schema.json`` is Draft 2020-12 valid.
  2. Markdown fixtures under ``fixtures/relations/`` expose a
     ``$pkm.relations`` object that validates against that schema.
  3. ``schemas/v1/rpc/fleet-matrix.json`` is Draft 2020-12 valid and its
     ``methods`` catalog matches ``$defs.methodEntry`` plus per-method
     params/result schemas.

YAML frontmatter is extracted with a stdlib parser scoped to the
``$pkm.relations`` mapping so CI (`pip install ".[dev]"`) does not need
PyYAML.

Usage
  python tests/test_relations_spec.py
  python -m pytest tests/test_relations_spec.py -v --tb=short
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_SCHEMAS = _REPO_ROOT / "schemas"
_RELATIONS_SCHEMA = _SCHEMAS / "v1" / "relations" / "relations.schema.json"
_FLEET_MATRIX = _SCHEMAS / "v1" / "rpc" / "fleet-matrix.json"
_FIXTURES = _REPO_ROOT / "fixtures" / "relations"

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_ID_PREFIX = "https://bosunpkm.com/schemas/"

_REQUIRED_METHODS = (
    "yeoman.get_contact",
    "yeoman.list_cadence_due",
    "yeoman.record_interaction",
    "yeoman.update_channels",
    "trice.list_tasks",
    "trice.get_project_queue",
    "trice.toggle_task",
    "trice.reschedule_task",
    "logbook.get_agenda",
    "logbook.query_chronology",
    "logbook.append_log_entry",
    "logbook.block_time",
    "commonplace.resolve_id",
    "commonplace.search_shelf",
    "commonplace.update_status",
    "commonplace.append_highlight",
)

# Mirrors harbormaster apps/harbormaster/tests/test_method_matrix.py VALID_PARAMS.
_CONTACT_ID = "123e4567-e89b-42d3-a456-426614174000"
_VALID_RPC_PARAMS = {
    "yeoman.get_contact": {"id": _CONTACT_ID},
    "yeoman.list_cadence_due": {"as_of": "2026-09-16"},
    "yeoman.record_interaction": {
        "title": "Archive meeting",
        "occurred_at": "2026-09-16T14:00:00Z",
        "contact_id": _CONTACT_ID,
    },
    "yeoman.update_channels": {"id": _CONTACT_ID, "emails": ["ada@example.org"]},
    "trice.list_tasks": {"vault_root": "C:/vault", "path": "notes"},
    "trice.get_project_queue": {"id": "project-alpha"},
    "trice.toggle_task": {
        "vault_root": "C:/vault",
        "path": "notes/today.md",
        "marker_byte_offset": 3,
        "state": "done",
    },
    "trice.reschedule_task": {"id": "task-1", "due": "2026-09-20"},
    "logbook.get_agenda": {"vault_root": "C:/vault", "date": "2026-09-16"},
    "logbook.query_chronology": {"start": "2026-09-01", "end": "2026-09-16"},
    "logbook.append_log_entry": {"date": "2026-09-16", "body": "Standup notes"},
    "logbook.block_time": {
        "title": "Deep work",
        "start": "2026-09-16T09:00:00Z",
        "all_day": False,
    },
    "commonplace.resolve_id": {"external_ids": {"imdb": "tt0054387"}},
    "commonplace.search_shelf": {"query": "time machine", "medium": "book"},
    "commonplace.update_status": {"slug": "the-time-machine", "status": "reading"},
    "commonplace.append_highlight": {
        "slug": "the-time-machine",
        "text": "The Time Traveller",
    },
}

_REQUIRED_FIXTURES = (
    "task-delegated.md",
    "event-attended.md",
)

_CANONICAL_URN = re.compile(
    r"^urn:(qtm|logbook|yeoman|trice):(tx|event|contact|task):[0-9a-fA-F-]{36}$"
)
_CLOSING_FENCE = re.compile(r"\n---[ \t]*(?:\n|$)")


def _load_json(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _frontmatter_text(markdown: str) -> str:
    if not markdown.startswith("---"):
        raise ValueError("markdown fixture must start with YAML frontmatter (---)")
    rest = markdown[3:]
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    else:
        raise ValueError("malformed opening frontmatter fence")
    closer = _CLOSING_FENCE.search("\n" + rest)
    if closer is None:
        raise ValueError("markdown fixture is missing the closing --- fence")
    # Search used a synthetic leading newline so the span maps back with -1.
    return rest[: closer.start()]


def _unquote_scalar(text: str):
    value = text.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if value in ("[]",):
        return []
    if value in ("{}",):
        return {}
    if value in ("null", "~"):
        return None
    return value


def extract_pkm_relations(markdown: str) -> dict:
    """Return the `$pkm.relations` mapping from YAML frontmatter.

    Nested form (canonical in this repo):

        $pkm:
          relations:
            assignedToContact: urn:yeoman:contact:<uuid>
    """
    lines = _frontmatter_text(markdown).splitlines()
    pkm_indent = None
    rel_indent = None
    block: list[str] = []
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if pkm_indent is None:
            if stripped == "$pkm:" or stripped.startswith("$pkm:"):
                pkm_indent = indent
            continue
        if rel_indent is None:
            if indent <= pkm_indent:
                break
            if stripped == "relations:" or stripped.startswith("relations:"):
                rel_indent = indent
                rest = stripped[len("relations:") :].strip()
                if rest:
                    parsed = _unquote_scalar(rest)
                    if parsed in ({}, None):
                        return {}
                    raise ValueError(
                        "inline $pkm.relations values are not supported: "
                        f"{rest!r}"
                    )
            continue
        if indent <= rel_indent:
            break
        block.append(raw)
    if pkm_indent is None:
        raise ValueError("frontmatter is missing $pkm")
    if rel_indent is None:
        raise ValueError("frontmatter is missing $pkm.relations")
    return _parse_relations_block(block, rel_indent)


def _parse_relations_block(lines: list[str], parent_indent: int) -> dict:
    result: dict = {}
    index = 0
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if indent <= parent_indent:
            break
        if stripped.startswith("- "):
            raise ValueError("unexpected list item at $pkm.relations root")
        key, separator, rest = stripped.partition(":")
        if not separator:
            raise ValueError(f"expected 'key:' in relations block, got {stripped!r}")
        key = key.strip()
        rest = rest.strip()
        if rest:
            result[key] = _unquote_scalar(rest)
            index += 1
            continue
        items: list = []
        saw_list = False
        index += 1
        while index < len(lines):
            nxt = lines[index]
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                index += 1
                continue
            nested_indent = len(nxt) - len(nxt.lstrip(" "))
            nested = nxt.strip()
            if nested_indent <= indent:
                break
            if nested.startswith("- "):
                saw_list = True
                items.append(_unquote_scalar(nested[2:]))
                index += 1
                continue
            raise ValueError(f"unsupported nested mapping under {key}")
        result[key] = items if saw_list else {}
    return result


def _subschema(root: dict, ref: str) -> dict:
    return {
        "$schema": root["$schema"],
        "$defs": root["$defs"],
        "$ref": ref,
    }


class TestRelationsSpec(unittest.TestCase):
    """Typed `$pkm.relations` fixtures and JSON-RPC fleet matrix catalog."""

    @classmethod
    def setUpClass(cls):
        cls.relations_schema = _load_json(_RELATIONS_SCHEMA)
        cls.fleet_matrix = _load_json(_FLEET_MATRIX)

    def test_required_files_exist(self):
        self.assertTrue(_RELATIONS_SCHEMA.is_file(), _RELATIONS_SCHEMA)
        self.assertTrue(_FLEET_MATRIX.is_file(), _FLEET_MATRIX)
        for name in _REQUIRED_FIXTURES:
            path = _FIXTURES / name
            self.assertTrue(path.is_file(), path)

    def test_relations_schema_pins_draft_and_canonical_id(self):
        self.assertEqual(self.relations_schema.get("$schema"), _DRAFT_2020_12)
        expected_id = _ID_PREFIX + "v1/relations/relations.schema.json"
        self.assertEqual(self.relations_schema.get("$id"), expected_id)
        self.assertEqual(self.relations_schema.get("additionalProperties"), False)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_relations_schema_passes_meta_schema(self):
        try:
            Draft202012Validator.check_schema(self.relations_schema)
        except jsonschema.SchemaError as exc:
            self.fail(f"relations.schema.json failed Draft 2020-12 check: {exc.message}")

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_fixtures_validate_pkm_relations(self):
        validator = Draft202012Validator(self.relations_schema)
        expected_predicates = {
            "task-delegated.md": "assignedToContact",
            "event-attended.md": "attendedEvent",
        }
        expected_prefixes = {
            "assignedToContact": "urn:yeoman:contact:",
            "attendedEvent": "urn:logbook:event:",
        }
        for name, predicate in expected_predicates.items():
            with self.subTest(fixture=name):
                markdown = (_FIXTURES / name).read_text(encoding="utf-8")
                relations = extract_pkm_relations(markdown)
                self.assertIsInstance(relations, dict)
                self.assertIn(predicate, relations)
                target = relations[predicate]
                self.assertIsInstance(target, str)
                self.assertTrue(target.startswith(expected_prefixes[predicate]))
                self.assertRegex(target, _CANONICAL_URN)
                validator.validate(relations)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_unknown_predicate_is_rejected(self):
        validator = Draft202012Validator(self.relations_schema)
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(
                {
                    "mentionsNote": (
                        "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000"
                    )
                }
            )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_wrong_realm_urn_is_rejected(self):
        validator = Draft202012Validator(self.relations_schema)
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(
                {
                    "attendedEvent": (
                        "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000"
                    )
                }
            )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_one_or_more_urn_array_is_accepted(self):
        validator = Draft202012Validator(self.relations_schema)
        validator.validate(
            {
                "waitingOnContact": [
                    "urn:yeoman:contact:123e4567-e89b-42d3-a456-426614174000",
                    "urn:yeoman:contact:550e8400-e29b-41d4-a716-446655440000",
                ]
            }
        )

    def test_fleet_matrix_pins_draft_and_canonical_id(self):
        self.assertEqual(self.fleet_matrix.get("$schema"), _DRAFT_2020_12)
        expected_id = _ID_PREFIX + "v1/rpc/fleet-matrix.json"
        self.assertEqual(self.fleet_matrix.get("$id"), expected_id)
        self.assertEqual(self.fleet_matrix.get("jsonrpc"), "2.0")
        self.assertEqual(self.fleet_matrix.get("transport"), "stdio-ndjson")

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_fleet_matrix_passes_meta_schema(self):
        try:
            Draft202012Validator.check_schema(self.fleet_matrix)
        except jsonschema.SchemaError as exc:
            self.fail(f"fleet-matrix.json failed Draft 2020-12 check: {exc.message}")

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_fleet_matrix_catalog_matches_method_entry_schema(self):
        methods = self.fleet_matrix.get("methods")
        self.assertIsInstance(methods, dict)
        self.assertEqual(sorted(methods), sorted(_REQUIRED_METHODS))
        self.assertEqual(set(_VALID_RPC_PARAMS), set(_REQUIRED_METHODS))
        entry_validator = Draft202012Validator(
            _subschema(self.fleet_matrix, "#/$defs/methodEntry")
        )
        for name in _REQUIRED_METHODS:
            with self.subTest(method=name):
                entry = methods[name]
                entry_validator.validate(entry)
                self.assertEqual(entry["method"], name)
                self.assertEqual(entry["request"]["jsonrpc"], "2.0")
                self.assertEqual(entry["request"]["method"], name)
                self.assertTrue(entry["request"]["id"]["required"])
                self.assertEqual(entry["request"]["params"]["style"], "by-name")
                params_ref = entry["request"]["params"]["schemaRef"]
                result_ref = entry["result"]["schemaRef"]
                Draft202012Validator(
                    _subschema(self.fleet_matrix, params_ref)
                ).validate(_VALID_RPC_PARAMS[name])
                self.assertIn(params_ref[len("#/$defs/") :], self.fleet_matrix["$defs"])
                self.assertIn(result_ref[len("#/$defs/") :], self.fleet_matrix["$defs"])
                for event in entry["broadcasts"]:
                    self.assertTrue(event["name"].startswith(f"info.{entry['vessel']}."))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestRelationsSpec)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
