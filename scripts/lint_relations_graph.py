"""scripts/lint_relations_graph.py
──────────────────────────────────
Directed URN graph integrity linter for a Bosun PKM vault.

Walks every markdown note under ``--vault`` and builds a graph of canonical
URNs ``urn:<realm>:<entity_type>:<uuid>``. Findings:

  1. Orphaned URN pointers — relation (or body) targets not defined by any note.
  2. Invalid cross-realm predicates — ``$pkm.relations`` verbs whose targets
     do not match ``schemas/v1/relations/relations.schema.json``.
  3. Illegal Careen/Trice stage-gate cycles — dependency loops among Careen
     and Trice notes (``actionItemDerivedFrom`` plus ``blocked_by`` /
     ``depends_on`` / ``blocks`` / ``waitingOn`` fields).

Usage
  python scripts/lint_relations_graph.py --vault fixtures/synthetic_vault
  python scripts/lint_relations_graph.py --vault PATH --json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_RELATIONS_SCHEMA = (
    _REPO_ROOT / "schemas" / "v1" / "relations" / "relations.schema.json"
)

# Canonical typed-relation identity: urn:<realm>:<entity_type>:<uuid>
_CANONICAL_URN = re.compile(
    r"urn:([a-z0-9_-]+):([a-z0-9_-]+):([0-9a-fA-F-]{36})"
)
_UUID_URN = re.compile(r"^urn:uuid:([0-9a-fA-F-]{36})$")
_BARE_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_CLOSING_FENCE = re.compile(r"\n---[ \t]*(?:\n|$)")

# Envelope $pkm.id is urn:uuid:<id>; relation targets use realm-typed URNs.
# A note therefore *defines* the typed aliases that relations.schema.json
# (and Careen stage-gate fields) actually point at.
_REALM_URN_ALIASES: dict[str, tuple[tuple[str, str], ...]] = {
    "yeoman": (("yeoman", "contact"),),
    "trice": (("trice", "task"),),
    "careen": (
        ("careen", "milestone"),
        ("careen", "card"),
        ("careen", "project"),
    ),
    "logbook": (("logbook", "event"),),
    "quartermaster": (("qtm", "tx"),),
    "qtm": (("qtm", "tx"),),
    "charthouse": (("charthouse", "lore"),),
}

STAGE_GATE_REALMS = frozenset({"careen", "trice"})

# Typed $pkm.relations verb from relations.schema.json that participates in
# Careen/Trice stage-gate graphs, plus Trice/Careen frontmatter dependency
# fields. waitingOnContact is *not* included: it targets Yeoman contacts.
STAGE_GATE_PREDICATES = frozenset(
    {
        "actionItemDerivedFrom",
        "blocked_by",
        "depends_on",
        "depends-on",
        "blocks",
        "waitingOn",
    }
)

_STAGE_GATE_FIELDS = (
    "blocked_by",
    "depends_on",
    "depends-on",
    "blocks",
    "waitingOn",
)


@dataclass
class Finding:
    category: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"category": self.category, "message": self.message}
        if self.path:
            payload["path"] = self.path
        return payload


@dataclass
class NoteRecord:
    path: pathlib.Path
    relpath: str
    realm: str | None
    pkm_id: str | None
    uuid: str | None
    defined_urns: set[str] = field(default_factory=set)
    relations: dict[str, list[str]] = field(default_factory=dict)
    stage_gate_edges: list[tuple[str, str]] = field(default_factory=list)
    body_urns: list[str] = field(default_factory=list)


@dataclass
class LintReport:
    vault: pathlib.Path
    notes: int = 0
    defined_urns: int = 0
    edges: int = 0
    orphans: list[Finding] = field(default_factory=list)
    invalid_predicates: list[Finding] = field(default_factory=list)
    cycles: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.orphans or self.invalid_predicates or self.cycles)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "vault": str(self.vault),
            "notes": self.notes,
            "defined_urns": self.defined_urns,
            "edges": self.edges,
            "orphans": [item.as_dict() for item in self.orphans],
            "invalid_predicates": [
                item.as_dict() for item in self.invalid_predicates
            ],
            "cycles": [item.as_dict() for item in self.cycles],
        }


def _load_json(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _resolve_ref(root: dict, ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref (expected in-document): {ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"unresolved $ref {ref}")
        node = node[part]
    return node


def _extract_urn_pattern(root: dict, spec: Any) -> str | None:
    """Walk a relations.schema.json subschema until a string `pattern` is found."""
    if not isinstance(spec, dict):
        return None
    if spec.get("type") == "string" and isinstance(spec.get("pattern"), str):
        return spec["pattern"]
    if "$ref" in spec:
        return _extract_urn_pattern(root, _resolve_ref(root, spec["$ref"]))
    for key in ("oneOf", "anyOf"):
        alts = spec.get(key)
        if isinstance(alts, list):
            for alt in alts:
                found = _extract_urn_pattern(root, alt)
                if found:
                    return found
    if spec.get("type") == "array" and "items" in spec:
        return _extract_urn_pattern(root, spec["items"])
    return None


def load_predicate_patterns(
    schema: dict | None = None,
) -> dict[str, re.Pattern[str]]:
    """Map each canonical predicate verb to its URN regex from relations.schema.json."""
    if schema is None:
        schema = _load_json(_RELATIONS_SCHEMA)
    patterns: dict[str, re.Pattern[str]] = {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("relations schema is missing properties")
    for verb, spec in properties.items():
        raw = _extract_urn_pattern(schema, spec)
        if not raw:
            raise ValueError(
                f"relations schema verb {verb!r} has no URN pattern"
            )
        patterns[str(verb)] = re.compile(raw)
    return patterns


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


def split_frontmatter(markdown: str) -> tuple[str, str]:
    """Return (frontmatter_text, body). Empty frontmatter if no opening fence."""
    if not markdown.startswith("---"):
        return "", markdown
    rest = markdown[3:]
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    else:
        return "", markdown
    closer = _CLOSING_FENCE.search("\n" + rest)
    if closer is None:
        return "", markdown
    fm = rest[: closer.start()]
    body = rest[closer.end() - 1 :]
    if body.startswith("\n"):
        body = body[1:]
    return fm, body


def extract_pkm_fields(markdown: str) -> dict[str, Any]:
    """Return ``id``, ``realm``, and ``relations`` from nested ``$pkm`` frontmatter.

    Stdlib parser (no PyYAML). Matches the canonical nesting used by realm
    fixtures: ``$pkm: { id, realm, relations: { verb: urn | [urn, ...] } }``.
    """
    fm, _body = split_frontmatter(markdown)
    if not fm:
        return {}
    lines = fm.splitlines()
    pkm_indent = None
    result: dict[str, Any] = {"relations": {}}
    index = 0
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if pkm_indent is None:
            if stripped == "$pkm:" or stripped.startswith("$pkm:"):
                pkm_indent = indent
            index += 1
            continue
        if indent <= pkm_indent:
            break
        key, separator, rest = stripped.partition(":")
        if not separator or stripped.startswith("- "):
            index += 1
            continue
        key = key.strip()
        rest = rest.strip()
        if key == "relations":
            rel_indent = indent
            relations: dict[str, Any] = {}
            if rest:
                parsed = _unquote_scalar(rest)
                result["relations"] = parsed if isinstance(parsed, dict) else {}
                index += 1
                continue
            index += 1
            while index < len(lines):
                nxt = lines[index]
                if not nxt.strip() or nxt.lstrip().startswith("#"):
                    index += 1
                    continue
                nested_indent = len(nxt) - len(nxt.lstrip(" "))
                nested = nxt.strip()
                if nested_indent <= rel_indent:
                    break
                if nested.startswith("- "):
                    index += 1
                    continue
                verb, verb_sep, verb_rest = nested.partition(":")
                if not verb_sep:
                    index += 1
                    continue
                verb = verb.strip()
                verb_rest = verb_rest.strip()
                if verb_rest:
                    relations[verb] = _unquote_scalar(verb_rest)
                    index += 1
                    continue
                items: list = []
                saw_list = False
                index += 1
                while index < len(lines):
                    item_line = lines[index]
                    if not item_line.strip() or item_line.lstrip().startswith("#"):
                        index += 1
                        continue
                    item_indent = len(item_line) - len(item_line.lstrip(" "))
                    item_stripped = item_line.strip()
                    if item_indent <= nested_indent:
                        break
                    if item_stripped.startswith("- "):
                        saw_list = True
                        items.append(_unquote_scalar(item_stripped[2:]))
                        index += 1
                        continue
                    break
                relations[verb] = items if saw_list else {}
            result["relations"] = relations
            continue
        if rest:
            result[key] = _unquote_scalar(rest)
        index += 1
    return result


def _parse_root_list_field(frontmatter: str, field_name: str) -> list[str]:
    """Parse a top-level YAML list or scalar field (blocked_by, depends_on, ...)."""
    values: list[str] = []
    lines = frontmatter.splitlines()
    prefix = f"{field_name}:"
    index = 0
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if indent != 0 or not stripped.startswith(prefix):
            index += 1
            continue
        rest = stripped[len(prefix) :].strip()
        if rest:
            parsed = _unquote_scalar(rest)
            if parsed in ([], {}, None, ""):
                return []
            if isinstance(parsed, str):
                return [parsed]
            return []
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
                item = _unquote_scalar(nested[2:])
                if isinstance(item, str) and item:
                    values.append(item)
            index += 1
        return values
    return values


def _normalize_targets(value: Any) -> list[str]:
    if value is None or value in ({}, []):
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _uuid_from_pkm_id(pkm_id: str | None) -> str | None:
    if not pkm_id or not isinstance(pkm_id, str):
        return None
    match = _UUID_URN.match(pkm_id)
    if match:
        return match.group(1)
    canonical = _CANONICAL_URN.fullmatch(pkm_id)
    if canonical:
        return canonical.group(3)
    if _BARE_UUID.match(pkm_id):
        return pkm_id
    return None


def defined_urns_for_note(
    pkm_id: str | None,
    realm: str | None,
    extra_urns: Iterable[str] = (),
) -> set[str]:
    """URNs this note is considered to define (identity + realm-typed aliases)."""
    defined: set[str] = set()
    if pkm_id:
        defined.add(pkm_id)
        canonical = _CANONICAL_URN.fullmatch(pkm_id)
        if canonical:
            defined.add(canonical.group(0))
    uuid_part = _uuid_from_pkm_id(pkm_id)
    if uuid_part and realm:
        for scheme, entity_type in _REALM_URN_ALIASES.get(realm, ()):
            defined.add(f"urn:{scheme}:{entity_type}:{uuid_part}")
    for urn in extra_urns:
        if _CANONICAL_URN.fullmatch(urn):
            defined.add(urn)
    return defined


def _iter_markdown(vault: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in vault.rglob("*.md") if path.is_file())


def parse_note(path: pathlib.Path, vault: pathlib.Path) -> NoteRecord:
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    pkm = extract_pkm_fields(text)
    realm = pkm.get("realm") if isinstance(pkm.get("realm"), str) else None
    pkm_id = pkm.get("id") if isinstance(pkm.get("id"), str) else None
    relations_raw = pkm.get("relations")
    relations: dict[str, list[str]] = {}
    if isinstance(relations_raw, dict):
        for verb, target in relations_raw.items():
            relations[str(verb)] = _normalize_targets(target)

    record = NoteRecord(
        path=path,
        relpath=str(path.relative_to(vault)).replace("\\", "/"),
        realm=realm,
        pkm_id=pkm_id,
        uuid=_uuid_from_pkm_id(pkm_id),
        relations=relations,
        defined_urns=defined_urns_for_note(pkm_id, realm),
    )

    relation_targets = {
        urn for targets in relations.values() for urn in targets
    }
    for match in _CANONICAL_URN.finditer(body):
        urn = match.group(0)
        if urn not in relation_targets:
            record.body_urns.append(urn)

    for field_name in _STAGE_GATE_FIELDS:
        for item in _parse_root_list_field(fm, field_name):
            match = _CANONICAL_URN.fullmatch(item)
            if match:
                record.stage_gate_edges.append((field_name, match.group(0)))

    for verb, targets in relations.items():
        if verb in STAGE_GATE_PREDICATES:
            for target in targets:
                if _CANONICAL_URN.fullmatch(target):
                    record.stage_gate_edges.append((verb, target))
    return record


def _urn_realm(urn: str) -> str | None:
    match = _CANONICAL_URN.fullmatch(urn)
    if not match:
        return None
    scheme = match.group(1)
    if scheme == "qtm":
        return "quartermaster"
    return scheme


def _is_stage_gate_node(record: NoteRecord) -> bool:
    if record.realm in STAGE_GATE_REALMS:
        return True
    return any(_urn_realm(urn) in STAGE_GATE_REALMS for urn in record.defined_urns)


def _find_cycles(graph: dict[str, list[tuple[str, str]]]) -> list[list[str]]:
    """Return simple directed cycles as node-id paths (including return to start)."""
    cycles: list[list[str]] = []
    seen_signatures: set[tuple[str, ...]] = set()
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def _canonical_cycle(path: list[str]) -> tuple[str, ...]:
        body = path[:-1]
        pivot = body.index(min(body))
        rotated = body[pivot:] + body[:pivot]
        return tuple(rotated)

    def dfs(node: str) -> None:
        visiting.add(node)
        stack.append(node)
        for _predicate, nxt in graph.get(node, []):
            if nxt in visiting:
                start = stack.index(nxt)
                cycle_path = stack[start:] + [nxt]
                signature = _canonical_cycle(cycle_path)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    cycles.append(cycle_path)
            elif nxt not in visited and nxt in graph:
                dfs(nxt)
            elif nxt not in visited and nxt not in graph:
                # Target may be an unresolved / non-stage-gate node; skip.
                continue
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        if node not in visited:
            dfs(node)
    return cycles


def lint_vault(
    vault: pathlib.Path,
    predicate_patterns: dict[str, re.Pattern[str]] | None = None,
) -> LintReport:
    """Lint every markdown note under ``vault`` and return a structured report."""
    vault = vault.resolve()
    report = LintReport(vault=vault)
    if not vault.is_dir():
        report.orphans.append(
            Finding(
                category="orphan",
                message=f"vault directory does not exist: {vault}",
            )
        )
        return report

    patterns = predicate_patterns or load_predicate_patterns()
    notes = [parse_note(path, vault) for path in _iter_markdown(vault)]
    report.notes = len(notes)

    defined: set[str] = set()
    urn_to_note: dict[str, NoteRecord] = {}
    for note in notes:
        defined.update(note.defined_urns)
        for urn in note.defined_urns:
            urn_to_note.setdefault(urn, note)
    report.defined_urns = len(defined)

    edge_count = 0
    stage_nodes: dict[str, NoteRecord] = {}
    stage_graph: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def _primary_id(note: NoteRecord) -> str:
        if note.pkm_id:
            return note.pkm_id
        if note.defined_urns:
            return sorted(note.defined_urns)[0]
        return note.relpath

    for note in notes:
        if _is_stage_gate_node(note):
            stage_nodes[_primary_id(note)] = note
            for urn in note.defined_urns:
                stage_nodes[urn] = note

    for note in notes:
        source_id = _primary_id(note)
        for verb, targets in note.relations.items():
            pattern = patterns.get(verb)
            for target in targets:
                edge_count += 1
                if pattern is None:
                    report.invalid_predicates.append(
                        Finding(
                            category="invalid_predicate",
                            path=note.relpath,
                            message=(
                                f"{verb} is not a canonical $pkm.relations verb "
                                f"(target {target})"
                            ),
                        )
                    )
                elif not pattern.fullmatch(target):
                    report.invalid_predicates.append(
                        Finding(
                            category="invalid_predicate",
                            path=note.relpath,
                            message=(
                                f"{verb} target {target} does not match "
                                f"canonical pattern {pattern.pattern}"
                            ),
                        )
                    )
                if target not in defined:
                    report.orphans.append(
                        Finding(
                            category="orphan",
                            path=note.relpath,
                            message=(
                                f"$pkm.relations.{verb} -> {target} "
                                "is not defined by any note in the vault"
                            ),
                        )
                    )
        for urn in note.body_urns:
            edge_count += 1
            if urn not in defined:
                report.orphans.append(
                    Finding(
                        category="orphan",
                        path=note.relpath,
                        message=(
                            f"body pointer {urn} is not defined by any note "
                            "in the vault"
                        ),
                    )
                )
        if _is_stage_gate_node(note):
            for predicate, target in note.stage_gate_edges:
                target_note = urn_to_note.get(target)
                if target_note is None or not _is_stage_gate_node(target_note):
                    continue
                stage_graph[source_id].append(
                    (predicate, _primary_id(target_note))
                )

    report.edges = edge_count

    for cycle in _find_cycles(stage_graph):
        report.cycles.append(
            Finding(
                category="cycle",
                message="Careen/Trice stage-gate cycle: " + " -> ".join(cycle),
            )
        )
    return report


def format_report(report: LintReport) -> str:
    lines = [
        "=" * 78,
        "BOSUN FLEET: URN Relation Graph Integrity",
        f"Vault: {report.vault}",
        f"Notes: {report.notes}    Defined URNs: {report.defined_urns}    Edges: {report.edges}",
        "=" * 78,
    ]

    def _section(title: str, findings: list[Finding]) -> None:
        lines.append("")
        lines.append(f"{title} ({len(findings)})")
        if not findings:
            lines.append("  (none)")
            return
        for item in findings:
            loc = f"{item.path}: " if item.path else ""
            lines.append(f"  - {loc}{item.message}")

    _section("ORPHANS", report.orphans)
    _section("INVALID PREDICATES", report.invalid_predicates)
    _section("CAREEN/TRICE STAGE-GATE CYCLES", report.cycles)
    lines.append("")
    lines.append("-" * 78)
    if report.ok:
        lines.append(
            "SUCCESS: relational integrity intact "
            "(no orphans, invalid predicates, or Careen/Trice cycles)."
        )
    else:
        total = (
            len(report.orphans)
            + len(report.invalid_predicates)
            + len(report.cycles)
        )
        lines.append(f"FAILURE: detected {total} finding(s).")
    lines.append("-" * 78)
    return "\n".join(lines)


def run_linter(vault: pathlib.Path, as_json: bool = False) -> int:
    if not vault.exists():
        message = f"error: vault path does not exist: {vault}"
        if as_json:
            print(json.dumps({"ok": False, "error": message}, indent=2))
        else:
            print(message, file=sys.stderr)
        return 2
    report = lint_vault(vault)
    if as_json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(format_report(report))
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Lint a vault's URN relation graph for orphans, illegal "
            "cross-realm predicates, and Careen/Trice stage-gate cycles."
        )
    )
    parser.add_argument(
        "--vault",
        required=True,
        type=pathlib.Path,
        help="Path to the vault directory to lint.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the integrity report as JSON.",
    )
    args = parser.parse_args(argv)
    return run_linter(args.vault, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
