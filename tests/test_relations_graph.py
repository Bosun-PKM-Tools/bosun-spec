"""tests/test_relations_graph.py
────────────────────────────────
Tests for the URN relation graph integrity linter.

Verifies:
  1. The golden vault at fixtures/synthetic_vault lints clean (exit 0).
  2. An orphaned relation target is reported.
  3. A predicate targeting the wrong realm/entity type is reported.
  4. A Careen/Trice stage-gate cycle (mutual actionItemDerivedFrom) is reported.
  5. CLI --json emits a structured report.

Usage
  python tests/test_relations_graph.py
  python -m pytest tests/test_relations_graph.py -v --tb=short
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lint_relations_graph import (
    load_predicate_patterns,
    lint_vault,
    run_linter,
)

_LINT_SCRIPT = _REPO_ROOT / "scripts" / "lint_relations_graph.py"
_GOLDEN_VAULT = _REPO_ROOT / "fixtures" / "synthetic_vault"

_ADA = "0191fa30-1002-7000-8000-0000000000aa"
_TASK_A = "0191fa30-1003-7000-8000-000000000031"
_TASK_B = "0191fa30-1003-7000-8000-000000000032"
_EVENT = "0191fa30-1004-7000-8000-000000000041"
_TX = "0191fa30-1005-7000-8000-000000000051"


def _note(
    *,
    title: str,
    realm: str,
    uuid_part: str,
    relations: dict[str, str] | None = None,
    extra_frontmatter: str = "",
    body: str | None = None,
) -> str:
    rel_lines = []
    if relations:
        for verb, target in relations.items():
            rel_lines.append(f"    {verb}: {target}")
    relations_block = (
        "\n".join(rel_lines) if rel_lines else "    {}"
    )
    extra = extra_frontmatter.rstrip() + "\n" if extra_frontmatter else ""
    body_text = body if body is not None else f"# {title}\n"
    return (
        f"---\n"
        f"title: {title}\n"
        f"{extra}"
        f"$pkm:\n"
        f"  id: urn:uuid:{uuid_part}\n"
        f"  realm: {realm}\n"
        f"  created_at: '2026-09-17T10:00:00Z'\n"
        f"  updated_at: '2026-09-17T11:00:00Z'\n"
        f"  relations:\n"
        f"{relations_block}\n"
        f"---\n\n"
        f"{body_text}"
    )


def _write(root: pathlib.Path, relpath: str, contents: str) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _closed_pair(root: pathlib.Path) -> None:
    """Two notes with a valid assignedToContact edge (no cycle)."""
    _write(
        root,
        "02-yeoman/contact.md",
        _note(title="Ada", realm="yeoman", uuid_part=_ADA),
    )
    _write(
        root,
        "03-trice/task.md",
        _note(
            title="Follow up",
            realm="trice",
            uuid_part=_TASK_A,
            relations={"assignedToContact": f"urn:yeoman:contact:{_ADA}"},
        ),
    )


class TestRelationsGraphLinter(unittest.TestCase):
    """URN graph orphans, illegal predicates, and Careen/Trice cycles."""

    def test_predicate_patterns_load_from_relations_schema(self):
        patterns = load_predicate_patterns()
        self.assertIn("assignedToContact", patterns)
        self.assertIn("actionItemDerivedFrom", patterns)
        self.assertIn("purchasedViaTx", patterns)
        self.assertTrue(
            patterns["assignedToContact"].fullmatch(
                f"urn:yeoman:contact:{_ADA}"
            )
        )
        self.assertFalse(
            patterns["assignedToContact"].fullmatch(
                f"urn:logbook:event:{_EVENT}"
            )
        )

    def test_golden_vault_is_clean(self):
        self.assertTrue(
            _GOLDEN_VAULT.is_dir(),
            f"missing golden vault: {_GOLDEN_VAULT}",
        )
        report = lint_vault(_GOLDEN_VAULT)
        self.assertEqual(
            report.orphans,
            [],
            [item.message for item in report.orphans],
        )
        self.assertEqual(
            report.invalid_predicates,
            [],
            [item.message for item in report.invalid_predicates],
        )
        self.assertEqual(
            report.cycles,
            [],
            [item.message for item in report.cycles],
        )
        self.assertTrue(report.ok)
        self.assertGreaterEqual(report.notes, 200)

    def test_cli_golden_vault_exits_zero(self):
        result = subprocess.run(
            [
                sys.executable,
                str(_LINT_SCRIPT),
                "--vault",
                str(_GOLDEN_VAULT),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Script failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("SUCCESS: relational integrity intact", result.stdout)

    def test_cli_json_report(self):
        result = subprocess.run(
            [
                sys.executable,
                str(_LINT_SCRIPT),
                "--vault",
                str(_GOLDEN_VAULT),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["orphans"], [])
        self.assertEqual(payload["invalid_predicates"], [])
        self.assertEqual(payload["cycles"], [])

    def test_cli_missing_vault_exits_two(self):
        missing = _REPO_ROOT / "fixtures" / "does-not-exist-vault"
        result = subprocess.run(
            [
                sys.executable,
                str(_LINT_SCRIPT),
                "--vault",
                str(missing),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exist", result.stderr)

    def test_detects_orphan_pointer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _closed_pair(root)
            _write(
                root,
                "03-trice/orphan.md",
                _note(
                    title="Orphan pointer",
                    realm="trice",
                    uuid_part=_TASK_B,
                    relations={
                        "assignedToContact": (
                            "urn:yeoman:contact:"
                            "00000000-0000-4000-8000-000000000099"
                        )
                    },
                ),
            )
            report = lint_vault(root)
            self.assertFalse(report.ok)
            self.assertTrue(report.orphans)
            self.assertTrue(
                any("00000000-0000-4000-8000-000000000099" in item.message for item in report.orphans)
            )
            self.assertEqual(report.invalid_predicates, [])
            self.assertEqual(report.cycles, [])

    def test_detects_invalid_cross_realm_predicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _write(
                root,
                "02-yeoman/contact.md",
                _note(title="Ada", realm="yeoman", uuid_part=_ADA),
            )
            _write(
                root,
                "04-logbook/event.md",
                _note(title="Standup", realm="logbook", uuid_part=_EVENT),
            )
            _write(
                root,
                "03-trice/wrong-realm.md",
                _note(
                    title="Wrong realm target",
                    realm="trice",
                    uuid_part=_TASK_A,
                    relations={
                        "assignedToContact": f"urn:logbook:event:{_EVENT}"
                    },
                ),
            )
            report = lint_vault(root)
            self.assertFalse(report.ok)
            self.assertTrue(report.invalid_predicates)
            self.assertTrue(
                any(
                    "assignedToContact" in item.message
                    and "urn:logbook:event:" in item.message
                    for item in report.invalid_predicates
                )
            )

    def test_detects_careen_trice_stage_gate_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _write(
                root,
                "02-yeoman/contact.md",
                _note(title="Ada", realm="yeoman", uuid_part=_ADA),
            )
            _write(
                root,
                "03-trice/task-a.md",
                _note(
                    title="Task A",
                    realm="trice",
                    uuid_part=_TASK_A,
                    relations={
                        "actionItemDerivedFrom": f"urn:trice:task:{_TASK_B}",
                        "assignedToContact": f"urn:yeoman:contact:{_ADA}",
                    },
                ),
            )
            _write(
                root,
                "03-trice/task-b.md",
                _note(
                    title="Task B",
                    realm="trice",
                    uuid_part=_TASK_B,
                    relations={
                        "actionItemDerivedFrom": f"urn:trice:task:{_TASK_A}",
                        "assignedToContact": f"urn:yeoman:contact:{_ADA}",
                    },
                ),
            )
            report = lint_vault(root)
            self.assertFalse(report.ok)
            self.assertEqual(report.invalid_predicates, [])
            self.assertEqual(report.orphans, [])
            self.assertTrue(report.cycles)
            self.assertTrue(
                any("stage-gate cycle" in item.message for item in report.cycles)
            )

    def test_blocked_by_cycle_is_a_stage_gate_finding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _write(
                root,
                "03-trice/task-a.md",
                _note(
                    title="Task A",
                    realm="trice",
                    uuid_part=_TASK_A,
                    extra_frontmatter=(
                        f"blocked_by:\n  - urn:trice:task:{_TASK_B}\n"
                    ),
                ),
            )
            _write(
                root,
                "03-trice/task-b.md",
                _note(
                    title="Task B",
                    realm="trice",
                    uuid_part=_TASK_B,
                    extra_frontmatter=(
                        f"blocked_by:\n  - urn:trice:task:{_TASK_A}\n"
                    ),
                ),
            )
            report = lint_vault(root)
            self.assertFalse(report.ok)
            self.assertTrue(report.cycles)

    def test_run_linter_helper_matches_cli_contract(self):
        code = run_linter(_GOLDEN_VAULT, as_json=False)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
