"""tests/benchmark_postel_coercion.py
───────────────────────────────────
High-throughput benchmark and unit verification for Postel envelope coercion.

Invariants Verified:
  1. Permissive input handling:
     - Date-only strings ('YYYY-MM-DD')
     - Missing seconds ('YYYY-MM-DDTHH:MMZ', 'YYYY-MM-DDTHH:MM')
     - Timezone offsets (+02:00, -04:00, etc.) normalized to UTC
     - Scalar strings where URN arrays are required
     - Bare UUIDs coerced to canonical UUID URNs
     - Realm whitespace / prefix normalization
  2. Conservative output:
     - Canonical RFC 3339 / ISO 8601 UTC timestamps ('YYYY-MM-DDTHH:MM:SSZ')
     - Validated canonical URN lists
     - Clean schema conformance against schemas/v1/meta/envelope.schema.json
  3. Throughput floor:
     - >100,000 operations/second across 10,000 synthetic envelopes
     - Sub-100ms total wall time (< 0.100s)

Usage:
  python tests/benchmark_postel_coercion.py
  python -m pytest tests/benchmark_postel_coercion.py -v
"""

from __future__ import annotations

import datetime
import json
import pathlib
import sys
import time
import unittest
from typing import Any, Dict, List

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.postel_coercion import (
    coerce_envelope,
    coerce_id,
    coerce_realm,
    coerce_relations,
    coerce_timestamp,
    coerce_urn_list,
    is_valid_urn,
    is_valid_uuid_urn,
    normalize_frontmatter,
)

try:
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_ENVELOPE_SCHEMA_PATH = (
    _REPO_ROOT / "schemas" / "v1" / "meta" / "envelope.schema.json"
)


class TestPostelCoercionUnit(unittest.TestCase):
    """Unit tests for Postel normalization rules and edge cases."""

    def test_coerce_timestamp_variations(self):
        """Coerces date-only, missing seconds, offsets, and objects into UTC RFC 3339."""
        # 1. Date-only -> midnight UTC
        self.assertEqual(
            coerce_timestamp("2026-09-16"), "2026-09-16T00:00:00Z"
        )
        self.assertEqual(
            coerce_timestamp(datetime.date(2026, 9, 16)), "2026-09-16T00:00:00Z"
        )

        # 2. Missing seconds
        self.assertEqual(
            coerce_timestamp("2026-09-16T12:00Z"), "2026-09-16T12:00:00Z"
        )
        self.assertEqual(
            coerce_timestamp("2026-09-16T12:00"), "2026-09-16T12:00:00Z"
        )

        # 3. Full timestamp without Z
        self.assertEqual(
            coerce_timestamp("2026-09-16T12:00:00"), "2026-09-16T12:00:00Z"
        )

        # 4. Canonical RFC 3339 UTC
        self.assertEqual(
            coerce_timestamp("2026-09-16T12:00:00Z"), "2026-09-16T12:00:00Z"
        )

        # 5. Space delimiter (SQL / Git log style)
        self.assertEqual(
            coerce_timestamp("2026-09-16 12:00:00"), "2026-09-16T12:00:00Z"
        )
        self.assertEqual(
            coerce_timestamp("2026-09-16 12:00"), "2026-09-16T12:00:00Z"
        )

        # 6. Timezone offsets normalized to UTC
        self.assertEqual(
            coerce_timestamp("2026-09-16T14:30:00+02:00"), "2026-09-16T12:30:00Z"
        )
        self.assertEqual(
            coerce_timestamp("2026-09-16T14:30+02:00"), "2026-09-16T12:30:00Z"
        )
        self.assertEqual(
            coerce_timestamp("2026-09-16T08:00:00-04:00"), "2026-09-16T12:00:00Z"
        )

        # 7. Fractional seconds ending in Z
        self.assertEqual(
            coerce_timestamp("2026-09-16T12:00:00.123Z"), "2026-09-16T12:00:00.123Z"
        )

        # 8. Python datetime
        dt_naive = datetime.datetime(2026, 9, 16, 12, 0, 0)
        self.assertEqual(coerce_timestamp(dt_naive), "2026-09-16T12:00:00Z")

    def test_coerce_timestamp_invalid_rejected(self):
        """Invalid timestamp representations raise ValueError."""
        invalid_cases = ["not-a-date", "2026/09/16", "yesterday", ""]
        for item in invalid_cases:
            with self.subTest(invalid=item):
                with self.assertRaises(ValueError):
                    coerce_timestamp(item)

    def test_coerce_urn_list(self):
        """Coerces scalar strings and iterables into validated URN lists."""
        urn_a = "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
        urn_b = "urn:logbook:event:018f62f8-9a3b-7d23-bf72-5b9c03bfba44"

        # Scalar string -> list of 1
        self.assertEqual(coerce_urn_list(urn_a), [urn_a])

        # List -> list
        self.assertEqual(coerce_urn_list([urn_a, urn_b]), [urn_a, urn_b])

        # Comma-separated string -> list of 2
        self.assertEqual(
            coerce_urn_list(f"{urn_a}, {urn_b}"), [urn_a, urn_b]
        )

        # None or empty string -> empty list
        self.assertEqual(coerce_urn_list(None), [])
        self.assertEqual(coerce_urn_list(""), [])
        self.assertEqual(coerce_urn_list([]), [])

    def test_coerce_urn_list_invalid_rejected(self):
        """Invalid URN strings raise ValueError."""
        with self.assertRaises(ValueError):
            coerce_urn_list("not-a-urn")
        with self.assertRaises(ValueError):
            coerce_urn_list(["urn:valid:1", "http://not-a-urn"])

    def test_coerce_id_variations(self):
        """Coerces bare UUIDs and un-prefixed UUIDs to lowercase urn:uuid:."""
        uuid_str = "018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
        expected = f"urn:uuid:{uuid_str}"

        # Bare UUID
        self.assertEqual(coerce_id(uuid_str), expected)
        # Uppercase bare UUID
        self.assertEqual(coerce_id(uuid_str.upper()), expected)
        # uuid: prefix
        self.assertEqual(coerce_id(f"uuid:{uuid_str}"), expected)
        # urn:uuid: prefix
        self.assertEqual(coerce_id(f"urn:uuid:{uuid_str}"), expected)
        self.assertEqual(coerce_id(f"urn:uuid:{uuid_str.upper()}"), expected)

    def test_coerce_realm_variations(self):
        """Coerces whitespace, uppercase, and numeric prefixes."""
        self.assertEqual(coerce_realm("  HARBOR  "), "harbor")
        self.assertEqual(coerce_realm("06-harbor"), "harbor")
        self.assertEqual(coerce_realm("50-relay"), "relay")
        self.assertEqual(coerce_realm("quartermaster"), "quartermaster")

    def test_coerce_relations(self):
        """Coerces relations dictionary verbs to validated lists."""
        raw = {
            "assignedToContact": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "attendedEvent": ["urn:logbook:event:018f62f8-9a3b-7d23-bf72-5b9c03bfba44"],
            "emptyPredicate": None,
        }
        res = coerce_relations(raw)
        self.assertEqual(
            res["assignedToContact"],
            ["urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"],
        )
        self.assertEqual(
            res["attendedEvent"],
            ["urn:logbook:event:018f62f8-9a3b-7d23-bf72-5b9c03bfba44"],
        )
        self.assertEqual(res["emptyPredicate"], [])

    def test_coerce_envelope_full(self):
        """Full envelope normalization produces canonical envelope."""
        envelope = {
            "id": "018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
            "realm": "06-HARBOR",
            "created_at": "2026-09-16",
            "updated_at": "2026-09-16T12:00Z",
            "relations": {
                "assignedToContact": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
            },
        }
        coerced = coerce_envelope(envelope)
        self.assertEqual(
            coerced["id"], "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
        )
        self.assertEqual(coerced["realm"], "harbor")
        self.assertEqual(coerced["created_at"], "2026-09-16T00:00:00Z")
        self.assertEqual(coerced["updated_at"], "2026-09-16T12:00:00Z")
        self.assertEqual(
            coerced["relations"]["assignedToContact"],
            ["urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"],
        )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema not installed")
    def test_coerced_envelope_validates_against_meta_schema(self):
        """Coerced envelopes must strictly validate against envelope.schema.json."""
        with open(_ENVELOPE_SCHEMA_PATH, encoding="utf-8") as fh:
            schema_obj = json.load(fh)
        validator = Draft202012Validator(schema_obj)

        permissive_inputs = [
            {
                "id": "018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "realm": "03-trice",
                "created_at": "2026-09-16",
                "updated_at": "2026-09-16",
                "relations": {
                    "actionItemDerivedFrom": "urn:trice:task:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
                },
            },
            {
                "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba44",
                "realm": "QUARTERMASTER",
                "created_at": "2026-09-16T14:30:00+02:00",
                "updated_at": "2026-09-16T12:00Z",
                "relations": {
                    "purchasedViaTx": "urn:qtm:tx:018f62f8-9a3b-7d23-bf72-5b9c03bfba45"
                },
            },
        ]

        for raw_env in permissive_inputs:
            coerced_env = coerce_envelope(raw_env)
            # Schema expects {"$pkm": envelope}
            wrapped = {"$pkm": coerced_env}
            validator.validate(wrapped)


class BenchmarkPostelCoercion(unittest.TestCase):
    """High-throughput benchmark across 10,000 synthetic envelopes."""

    def setUp(self):
        self.count = 10_000
        self.throughput_floor = 100_000.0  # ops/sec
        self.max_wall_time_seconds = 0.100  # 100ms

        # Generate a balanced mixture of permissive synthetic envelope variations
        patterns = [
            # Pattern A: Date-only + scalar URN
            {
                "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "realm": "harbor",
                "created_at": "2026-09-16",
                "updated_at": "2026-09-16",
                "relations": {
                    "assignedToContact": "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
                },
            },
            # Pattern B: Missing seconds + list URN
            {
                "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "realm": "yeoman",
                "created_at": "2026-09-16T12:00Z",
                "updated_at": "2026-09-16T12:00Z",
                "relations": {
                    "attendedEvent": [
                        "urn:logbook:event:018f62f8-9a3b-7d23-bf72-5b9c03bfba44"
                    ]
                },
            },
            # Pattern C: Missing seconds no Z + bare UUID + uppercase realm
            {
                "id": "018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "realm": "03-TRICE",
                "created_at": "2026-09-16T12:00",
                "updated_at": "2026-09-16T12:00",
                "relations": {
                    "actionItemDerivedFrom": "urn:trice:task:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
                },
            },
            # Pattern D: UTC offset + multi-relation dictionary
            {
                "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "realm": "quartermaster",
                "created_at": "2026-09-16T14:30:00+02:00",
                "updated_at": "2026-09-16T08:00:00-04:00",
                "relations": {
                    "purchasedViaTx": "urn:qtm:tx:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                    "consultedProvider": [
                        "urn:yeoman:contact:018f62f8-9a3b-7d23-bf72-5b9c03bfba43"
                    ],
                },
            },
            # Pattern E: Canonical RFC 3339 UTC + empty relations
            {
                "id": "urn:uuid:018f62f8-9a3b-7d23-bf72-5b9c03bfba43",
                "realm": "careen",
                "created_at": "2026-09-16T12:00:00Z",
                "updated_at": "2026-09-16T12:00:00Z",
                "relations": {},
            },
        ]

        self.synthetic_envelopes: List[Dict[str, Any]] = []
        for i in range(self.count):
            base = patterns[i % len(patterns)]
            # Deep copy to ensure isolated inputs
            env = {
                "id": base["id"],
                "realm": base["realm"],
                "created_at": base["created_at"],
                "updated_at": base["updated_at"],
                "relations": dict(base["relations"]),
            }
            self.synthetic_envelopes.append(env)

    def test_benchmark_throughput_floor_and_latency(self):
        """Benchmark 10,000 synthetic envelopes asserting >100k ops/sec and sub-100ms wall time."""
        envelopes = self.synthetic_envelopes

        # Warm-up run (1,000 items)
        for i in range(1_000):
            coerce_envelope(envelopes[i])

        # Benchmark execution
        t0 = time.perf_counter()
        results = [coerce_envelope(env) for env in envelopes]
        t1 = time.perf_counter()

        wall_time = t1 - t0
        throughput = len(envelopes) / wall_time
        avg_latency_us = (wall_time / len(envelopes)) * 1_000_000

        # Verify integrity of coerced outputs
        self.assertEqual(len(results), self.count)
        sample = results[0]
        self.assertTrue(sample["created_at"].endswith("Z"))
        self.assertTrue(sample["updated_at"].endswith("Z"))
        self.assertTrue(sample["id"].startswith("urn:uuid:"))
        self.assertIsInstance(sample["relations"]["assignedToContact"], list)

        # Print benchmark metrics
        print()
        print("=" * 78)
        print("POSTEL COERCION BENCHMARK REPORT (10,000 Synthetic Envelopes)")
        print("=" * 78)
        print(f"Total Envelopes Processed : {len(envelopes):,}")
        print(f"Total Wall Clock Time     : {wall_time * 1000:.2f} ms ({wall_time:.4f} s)")
        print(f"Average Latency / Op      : {avg_latency_us:.2f} us")
        print(f"Achieved Throughput       : {throughput:,.0f} ops/sec")
        print(f"Throughput Floor Target   : >{self.throughput_floor:,.0f} ops/sec")
        print(f"Wall Time Ceiling Target  : <{self.max_wall_time_seconds * 1000:.1f} ms")
        print("-" * 78)

        # Strict assertion checks
        self.assertLess(
            wall_time,
            self.max_wall_time_seconds,
            f"Wall time exceeded ceiling: {wall_time * 1000:.2f}ms >= {self.max_wall_time_seconds * 1000:.1f}ms",
        )
        self.assertGreater(
            throughput,
            self.throughput_floor,
            f"Throughput fell below floor: {throughput:,.0f} ops/sec <= {self.throughput_floor:,.0f} ops/sec",
        )
        print(
            f"STATUS: PASS (sub-100ms wall time and >100,000 ops/sec floor satisfied)"
        )
        print("=" * 78)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPostelCoercionUnit))
    suite.addTests(loader.loadTestsFromTestCase(BenchmarkPostelCoercion))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
