"""scripts/bench_graph_traversal.py
─────────────────────────────────
Vault Graph Traversal Latency & Adjacency Benchmarks.

Invariants Verified:
  1. Graph queries conform strictly to schemas/v1/query/graph-dsl.schema.json.
  2. Traversal depth up to 5 hops across 10,000 synthetic edges in <20ms.

Evaluations:
  - Synthetic scale-free directed acyclic graph (1,000 nodes, 10,000 edges).
  - Single-hop (1-hop) query traversal latency.
  - K-hop (2-hop, 3-hop, 4-hop, 5-hop) traversal latency and subgraph projection.
  - Shortest-path point-to-point traversal query latency.
  - Subgraph adjacency matrix projection construction time.
  - Latency ceiling assertion (<20.0ms for 5-hop path).

Usage:
  python scripts/bench_graph_traversal.py
  python scripts/bench_graph_traversal.py --verbose
  python scripts/bench_graph_traversal.py --ceiling-ms 20.0
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.graph_query import (
    Edge,
    GraphQueryEngine,
    Node,
    VaultGraph,
)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "graph-dsl.schema.json"
LATENCY_CEILING_5_HOP_MS = 20.0

REALMS = ("careen", "trice", "yeoman", "quartermaster", "charthouse")
PREDICATES = (
    "depends_on",
    "assignedToContact",
    "purchasedViaTx",
    "campaign_lore_node",
    "actionItemDerivedFrom",
    "blocks",
    "waitingOn",
    "wikilink",
)


def generate_scale_free_dag(
    num_nodes: int = 1000,
    target_edges: int = 10000,
    seed: int = 42,
) -> Tuple[VaultGraph, List[str], List[Tuple[int, int]]]:
    """Generate a synthetic scale-free directed acyclic graph (DAG).

    Uses preferential attachment where edge source u < target v guarantees acyclicity.
    Returns:
      (graph, list_of_node_urns, list_of_raw_edge_tuples)
    """
    rng = random.Random(seed)
    graph = VaultGraph()
    node_urns: List[str] = []

    # 1. Create exactly num_nodes nodes
    for idx in range(num_nodes):
        node_uuid = str(uuid.UUID(int=idx + 1))
        realm = REALMS[idx % len(REALMS)]
        node_urn = f"urn:bosun:bench:{node_uuid}"
        node = Node(
            id=node_urn,
            realm=realm,
            title=f"Benchmark Task Entity {idx:04d}",
            path=f"bench/node_{idx:04d}.md",
            attributes={
                "index": idx,
                "priority": idx % 5,
                "kanban_stage": "active" if idx % 2 == 0 else "backlog",
            },
        )
        graph.add_node(node)
        node_urns.append(node_urn)

    # 2. Generate exactly target_edges using preferential attachment (DAG: u < v)
    edges_set: Set[Tuple[int, int]] = set()
    attachment_pool: List[int] = [0]

    # Initial spanning tree to connect nodes
    for v in range(1, num_nodes):
        u = rng.choice(attachment_pool)
        edges_set.add((u, v))
        attachment_pool.extend([u, v])

    # Fill remaining edges up to target_edges via preferential attachment
    max_attempts = target_edges * 50
    attempts = 0
    while len(edges_set) < target_edges and attempts < max_attempts:
        attempts += 1
        u = rng.choice(attachment_pool)
        v = rng.choice(attachment_pool)
        if u > v:
            u, v = v, u
        if u < v and (u, v) not in edges_set:
            edges_set.add((u, v))
            attachment_pool.extend([u, v])

    # If still below target_edges due to pool collisions, systematically fill
    if len(edges_set) < target_edges:
        for u in range(num_nodes):
            for v in range(u + 1, num_nodes):
                if (u, v) not in edges_set:
                    edges_set.add((u, v))
                    if len(edges_set) >= target_edges:
                        break
            if len(edges_set) >= target_edges:
                break

    # Add edges into VaultGraph
    raw_edges = sorted(edges_set)
    for u_idx, v_idx in raw_edges:
        predicate = PREDICATES[(u_idx + v_idx) % len(PREDICATES)]
        edge_type = "wikilink" if predicate == "wikilink" else "relation"
        edge = Edge(
            source=node_urns[u_idx],
            target=node_urns[v_idx],
            predicate=predicate,
            direction="outbound",
            edge_type=edge_type,
            weight=1.0,
        )
        graph.add_edge(edge)

    return graph, node_urns, raw_edges


def load_validator() -> Optional[Any]:
    """Load JSON Schema Draft 2020-12 validator for graph-dsl schema."""
    if not _HAS_JSONSCHEMA or not _SCHEMA_PATH.exists():
        return None
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    return Draft202012Validator(schema)


def evaluate_query(
    engine: GraphQueryEngine,
    query: Dict[str, Any],
    validator: Optional[Any] = None,
    iterations: int = 5,
) -> Dict[str, Any]:
    """Execute a query multiple times, record latencies, and optionally validate against schema."""
    if validator:
        validator.validate(query)

    latencies_ms: List[float] = []
    last_result: Dict[str, Any] = {}

    # Warm-up run
    last_result = engine.execute(query)
    if validator:
        validator.validate(last_result)

    # Benchmark runs
    for _ in range(iterations):
        t0 = time.perf_counter()
        last_result = engine.execute(query)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    mean_latency = sum(latencies_ms) / len(latencies_ms)
    min_latency = min(latencies_ms)
    max_latency = max(latencies_ms)

    return {
        "query": query,
        "result": last_result,
        "iterations": iterations,
        "mean_latency_ms": round(mean_latency, 3),
        "min_latency_ms": round(min_latency, 3),
        "max_latency_ms": round(max_latency, 3),
        "node_count": len(last_result.get("nodes", [])),
        "edge_count": len(last_result.get("edges", [])),
    }


def run_traversal_benchmarks(
    num_nodes: int = 1000,
    target_edges: int = 10000,
    iterations: int = 5,
    ceiling_ms: float = LATENCY_CEILING_5_HOP_MS,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Execute standard suite of graph traversal benchmarks and assert ceiling."""
    validator = load_validator()

    t_build_0 = time.perf_counter()
    graph, node_urns, raw_edges = generate_scale_free_dag(
        num_nodes=num_nodes,
        target_edges=target_edges,
        seed=42,
    )
    t_build_1 = time.perf_counter()
    graph_build_ms = (t_build_1 - t_build_0) * 1000.0

    engine = GraphQueryEngine(graph)
    hub_node_urn = node_urns[0]

    # Find a multi-hop destination node for shortest path evaluation
    dest_node_urn = node_urns[num_nodes - 1]
    for candidate_idx in range(500, num_nodes):
        candidate_urn = node_urns[candidate_idx]
        sp = engine.find_shortest_path(hub_node_urn, candidate_urn, max_depth=5)
        if sp and len(sp) >= 3:
            dest_node_urn = candidate_urn
            break

    benchmark_results: Dict[str, Any] = {
        "num_nodes": len(node_urns),
        "num_edges": len(raw_edges),
        "graph_build_ms": round(graph_build_ms, 2),
        "ceiling_5_hop_ms": ceiling_ms,
        "benchmarks": {},
    }

    # 1. Single-hop query (max_depth=1)
    q_single_hop = {
        "query_id": "bench-single-hop-01",
        "linked_from": hub_node_urn,
        "max_depth": 1,
        "direction": "outbound",
        "projections": ["nodes", "edges"],
    }
    benchmark_results["benchmarks"]["1_hop"] = evaluate_query(
        engine, q_single_hop, validator=validator, iterations=iterations
    )

    # 2. Multi-hop queries (k = 2, 3, 4, 5)
    for k in (2, 3, 4, 5):
        q_k_hop = {
            "query_id": f"bench-{k}-hop",
            "linked_from": hub_node_urn,
            "max_depth": k,
            "direction": "outbound",
            "projections": ["nodes", "edges"],
        }
        benchmark_results["benchmarks"][f"{k}_hop"] = evaluate_query(
            engine, q_k_hop, validator=validator, iterations=iterations
        )

    # 3. 5-hop query WITH subgraph adjacency matrix projection
    q_5_hop_matrix = {
        "query_id": "bench-5-hop-adjacency-matrix",
        "linked_from": hub_node_urn,
        "max_depth": 5,
        "direction": "outbound",
        "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
    }
    benchmark_results["benchmarks"]["5_hop_matrix"] = evaluate_query(
        engine, q_5_hop_matrix, validator=validator, iterations=iterations
    )

    # 4. Shortest-path query
    q_shortest_path = {
        "query_id": "bench-shortest-path-01",
        "linked_from": hub_node_urn,
        "target_node": dest_node_urn,
        "max_depth": 5,
        "direction": "outbound",
        "projections": ["nodes", "edges", "shortest_path"],
    }
    benchmark_results["benchmarks"]["shortest_path"] = evaluate_query(
        engine, q_shortest_path, validator=validator, iterations=iterations
    )

    # Invariant assertion: 5-hop path traversal must be strictly under ceiling (<20ms)
    five_hop_latency = benchmark_results["benchmarks"]["5_hop"]["mean_latency_ms"]
    passed_ceiling = five_hop_latency < ceiling_ms
    benchmark_results["ceiling_passed"] = passed_ceiling

    if not passed_ceiling:
        raise AssertionError(
            f"5-hop graph traversal latency ceiling breached: "
            f"{five_hop_latency:.3f} ms >= {ceiling_ms:.1f} ms ceiling"
        )

    return benchmark_results


def format_report(results: Dict[str, Any]) -> str:
    """Format benchmark results into an executive terminal table."""
    lines = [
        "=" * 82,
        "BOSUN VAULT: GRAPH TRAVERSAL LATENCY & ADJACENCY BENCHMARKS",
        "=" * 82,
        f"Synthetic Scale-Free DAG : {results['num_nodes']:,} nodes | {results['num_edges']:,} edges",
        f"Graph Generation Time    : {results['graph_build_ms']:.2f} ms",
        f"5-Hop Latency Ceiling    : < {results['ceiling_5_hop_ms']:.1f} ms",
        "-" * 82,
        f"{'Benchmark Target':<28} {'Depth':<7} {'Nodes':<8} {'Edges':<8} {'Mean (ms)':<11} {'Min..Max (ms)':<14}",
        "-" * 82,
    ]

    benchmarks = results["benchmarks"]
    labels = [
        ("1_hop", "Single-Hop Traversal", "1"),
        ("2_hop", "2-Hop Subgraph", "2"),
        ("3_hop", "3-Hop Subgraph", "3"),
        ("4_hop", "4-Hop Subgraph", "4"),
        ("5_hop", "5-Hop Path Traversal", "5"),
        ("5_hop_matrix", "5-Hop + Adjacency Matrix", "5"),
        ("shortest_path", "Shortest-Path Query", "5"),
    ]

    for key, label, depth in labels:
        b = benchmarks.get(key)
        if not b:
            continue
        min_max = f"{b['min_latency_ms']:.2f}..{b['max_latency_ms']:.2f}"
        lines.append(
            f"{label:<28} {depth:<7} {b['node_count']:<8} {b['edge_count']:<8} "
            f"{b['mean_latency_ms']:<11.3f} {min_max:<14}"
        )

    lines.append("-" * 82)
    status_str = "PASS" if results.get("ceiling_passed") else "FAIL"
    five_hop_mean = benchmarks["5_hop"]["mean_latency_ms"]
    lines.append(
        f"5-Hop Latency: {five_hop_mean:.3f} ms | Ceiling: < {results['ceiling_5_hop_ms']:.1f} ms | STATUS: {status_str}"
    )
    lines.append("=" * 82)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vault Graph Traversal Benchmarks")
    parser.add_argument("--nodes", type=int, default=1000, help="Number of nodes (default: 1000)")
    parser.add_argument("--edges", type=int, default=10000, help="Number of edges (default: 10000)")
    parser.add_argument("--runs", type=int, default=5, help="Benchmark iterations (default: 5)")
    parser.add_argument("--ceiling-ms", type=float, default=LATENCY_CEILING_5_HOP_MS, help="Max allowed 5-hop latency")
    parser.add_argument("--json", action="store_true", help="Output raw JSON metrics")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics")
    args = parser.parse_args()

    results = run_traversal_benchmarks(
        num_nodes=args.nodes,
        target_edges=args.edges,
        iterations=args.runs,
        ceiling_ms=args.ceiling_ms,
        verbose=args.verbose,
    )

    if args.json:
        # Strip large raw outputs before printing JSON
        stripped = dict(results)
        stripped["benchmarks"] = {
            k: {
                "mean_latency_ms": v["mean_latency_ms"],
                "min_latency_ms": v["min_latency_ms"],
                "max_latency_ms": v["max_latency_ms"],
                "node_count": v["node_count"],
                "edge_count": v["edge_count"],
            }
            for k, v in results["benchmarks"].items()
        }
        print(json.dumps(stripped, indent=2))
    else:
        print(format_report(results))


if __name__ == "__main__":
    main()
