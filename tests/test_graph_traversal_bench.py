"""tests/test_graph_traversal_bench.py
───────────────────────────────────
Test suite and latency ceiling verification for Vault Graph Traversal.

Invariants Verified:
  1. Synthetic scale-free directed acyclic graph (1,000 nodes, 10,000 edges).
  2. Graph queries and result projections conform to schemas/v1/query/graph-dsl.schema.json.
  3. Single-hop, k-hop (2 to 5 hops), and shortest-path query evaluations.
  4. Traversal latency ceiling (<20ms for 5-hop path across 10,000 edges).

Usage:
  python tests/test_graph_traversal_bench.py
  python -m pytest tests/test_graph_traversal_bench.py -v
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
import unittest
from typing import Any, Dict, List, Set

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.bench_graph_traversal import (
    LATENCY_CEILING_5_HOP_MS,
    generate_scale_free_dag,
    run_traversal_benchmarks,
)
from scripts.graph_query import (
    GraphQueryEngine,
    VaultGraph,
)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "graph-dsl.schema.json"


class TestGraphTraversalBenchmarks(unittest.TestCase):
    """Unit tests and benchmark assertions for Vault Graph Traversal."""

    @classmethod
    def setUpClass(cls):
        cls.num_nodes = 1000
        cls.target_edges = 10000
        cls.graph, cls.node_urns, cls.raw_edges = generate_scale_free_dag(
            num_nodes=cls.num_nodes,
            target_edges=cls.target_edges,
            seed=42,
        )
        cls.engine = GraphQueryEngine(cls.graph)

        if _HAS_JSONSCHEMA and _SCHEMA_PATH.exists():
            with open(_SCHEMA_PATH, encoding="utf-8") as fh:
                cls.schema_json = json.load(fh)
            cls.validator = Draft202012Validator(cls.schema_json)
        else:
            cls.validator = None

    # -----------------------------------------------------------------------
    # Graph Topology & Scale-Free DAG Invariant Tests
    # -----------------------------------------------------------------------

    def test_synthetic_graph_exact_dimensions(self):
        """Graph must contain exactly 1,000 nodes and 10,000 edges."""
        self.assertEqual(len(self.graph.nodes), 1000)
        self.assertEqual(len(self.node_urns), 1000)
        self.assertEqual(len(self.raw_edges), 10000)

        total_out_edges = sum(len(edges) for edges in self.graph.out_edges.values())
        self.assertEqual(total_out_edges, 10000)

    def test_synthetic_graph_strictly_acyclic_dag(self):
        """All directed edges (u, v) must satisfy u < v ensuring acyclicity."""
        for u_idx, v_idx in self.raw_edges:
            self.assertLess(
                u_idx,
                v_idx,
                f"Edge ({u_idx} -> {v_idx}) violates topological ordering (u < v)",
            )

    def test_synthetic_graph_scale_free_hub_distribution(self):
        """Scale-free preferential attachment produces high-degree hubs."""
        degrees = [len(self.graph.out_edges.get(urn, [])) for urn in self.node_urns]
        max_degree = max(degrees)
        avg_degree = sum(degrees) / len(degrees)

        # Average degree is 10.0; scale-free hub must have degree >> average (typically > 100)
        self.assertAlmostEqual(avg_degree, 10.0, places=1)
        self.assertGreater(
            max_degree,
            100,
            f"Expected scale-free hub degree > 100, got max degree {max_degree}",
        )

    # -----------------------------------------------------------------------
    # Schema Conformance Tests
    # -----------------------------------------------------------------------

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_single_hop_query_conforms_to_schema(self):
        """Single-hop query and result conform to graph-dsl.schema.json."""
        query = {
            "query_id": "test-single-hop",
            "linked_from": self.node_urns[0],
            "max_depth": 1,
            "direction": "outbound",
            "projections": ["nodes", "edges"],
        }
        self.validator.validate(query)
        result = self.engine.execute(query)
        self.validator.validate(result)

        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertGreater(len(result["nodes"]), 0)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_k_hop_query_conforms_to_schema(self):
        """K-hop query with adjacency matrix conforms to graph-dsl.schema.json."""
        for k in (2, 3, 4, 5):
            with self.subTest(k=k):
                query = {
                    "query_id": f"test-k-hop-{k}",
                    "linked_from": self.node_urns[0],
                    "max_depth": k,
                    "direction": "outbound",
                    "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
                }
                self.validator.validate(query)
                result = self.engine.execute(query)
                self.validator.validate(result)

                self.assertIn("subgraph_adjacency_matrix", result)
                matrix_obj = result["subgraph_adjacency_matrix"]
                dim = matrix_obj["dimension"]
                self.assertEqual(len(matrix_obj["nodes"]), dim)
                self.assertEqual(len(matrix_obj["matrix"]), dim)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema package required")
    def test_shortest_path_query_conforms_to_schema(self):
        """Shortest-path query and result conform to graph-dsl.schema.json."""
        src_urn = self.node_urns[0]
        tgt_urn = self.node_urns[self.num_nodes - 1]

        query = {
            "query_id": "test-shortest-path",
            "linked_from": src_urn,
            "target_node": tgt_urn,
            "max_depth": 5,
            "direction": "outbound",
            "projections": ["nodes", "edges", "shortest_path"],
        }
        self.validator.validate(query)
        result = self.engine.execute(query)
        self.validator.validate(result)

        self.assertIn("shortest_path", result)
        if result["shortest_path"]:
            path = result["shortest_path"]
            self.assertEqual(path[0], src_urn)
            self.assertEqual(path[-1], tgt_urn)

    # -----------------------------------------------------------------------
    # Traversal Logic and Path Correctness Tests
    # -----------------------------------------------------------------------

    def test_find_shortest_path_finds_valid_edge_chain(self):
        """find_shortest_path returns a contiguous directed chain of edges."""
        src = self.node_urns[0]
        # Search for a candidate target reachable within 2-4 hops
        path = None
        for candidate_urn in self.node_urns[100:300]:
            candidate_path = self.engine.find_shortest_path(src, candidate_urn, max_depth=5)
            if candidate_path and len(candidate_path) >= 3:
                path = candidate_path
                break

        self.assertIsNotNone(path, "Failed to find any multi-hop path from root hub")
        self.assertGreaterEqual(len(path), 3)

        # Verify every step in path is an actual directed edge in the graph
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]
            out_targets = {e.target for e in self.graph.out_edges.get(u, [])}
            self.assertIn(v, out_targets, f"Broken path step: no edge {u} -> {v}")

    # -----------------------------------------------------------------------
    # Latency Ceiling Benchmark Assertion (< 20ms for 5-hop path)
    # -----------------------------------------------------------------------

    def test_5_hop_traversal_latency_below_ceiling(self):
        """5-hop path traversal across 10,000 edges must execute in < 20.0ms."""
        query = {
            "query_id": "bench-5-hop-latency-ceiling",
            "linked_from": self.node_urns[0],
            "max_depth": 5,
            "direction": "outbound",
            "projections": ["nodes", "edges"],
        }

        # Warm-up run
        self.engine.execute(query)

        # Timed evaluation across 5 runs
        latencies: List[float] = []
        for _ in range(5):
            t0 = time.perf_counter()
            res = self.engine.execute(query)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)

        mean_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)

        # Verify traversal visited the majority of the 10,000-edge scale-free graph
        self.assertGreaterEqual(len(res.get("nodes", [])), 500)
        self.assertGreaterEqual(len(res.get("edges", [])), 5000)

        # Assert strict latency ceiling (< 20.0 ms)
        self.assertLess(
            mean_latency,
            LATENCY_CEILING_5_HOP_MS,
            f"5-hop latency ceiling breached: mean {mean_latency:.3f}ms >= {LATENCY_CEILING_5_HOP_MS}ms",
        )
        self.assertLess(
            min_latency,
            LATENCY_CEILING_5_HOP_MS,
            f"5-hop min latency breached ceiling: {min_latency:.3f}ms",
        )

    def test_run_traversal_benchmarks_end_to_end(self):
        """run_traversal_benchmarks utility executes cleanly and returns ceiling_passed == True."""
        results = run_traversal_benchmarks(
            num_nodes=1000,
            target_edges=10000,
            iterations=3,
            ceiling_ms=LATENCY_CEILING_5_HOP_MS,
        )
        self.assertTrue(results["ceiling_passed"])
        self.assertIn("1_hop", results["benchmarks"])
        self.assertIn("5_hop", results["benchmarks"])
        self.assertIn("shortest_path", results["benchmarks"])
        self.assertLess(
            results["benchmarks"]["5_hop"]["mean_latency_ms"],
            LATENCY_CEILING_5_HOP_MS,
        )


if __name__ == "__main__":
    unittest.main()
