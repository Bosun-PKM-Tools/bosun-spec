"""scripts/graph_query.py
───────────────────────
Vault Graph Query DSL execution engine and compiler for Bosun PKM vaults.

Implements directional graph traversal over:
  - Typed `$pkm.relations` (e.g. assignedToContact, purchasedViaTx, campaign_lore_node).
  - Markdown wikilinks (`[[target-slug]]` or `[[urn:...]]`).
  - Stage-gate dependency links (blocks, blocked_by, depends_on).

Applies filters:
  - `match_realm`: filter by single or multiple realm identifiers.
  - `has_relation`: OR of relation predicates (string, list, or relationFilter).
  - `path`: ordered AND of relationFilter hops (every hop must match in sequence).
  - `linked_from`: origin root node URN(s) for directional traversal.
  - `max_depth`: maximum hop distance from origin.
  - `predicate_pattern`: regex pattern matching edge predicate labels.

Indexes notes by `$pkm.id` plus realm-typed URN aliases from
`lint_relations_graph.defined_urns_for_note` (e.g. `urn:careen:project:<uuid>`).

Computes projections conforming to schemas/v1/query/graph-dsl.schema.json:
  - `nodes`: list of vertex definitions with realm, title, depth, and attributes.
  - `edges`: list of directed links with source, target, predicate, direction, and type.
  - `subgraph_adjacency_matrix`: square N x N adjacency matrix indexed by ordered node URNs.

Usage:
  python scripts/graph_query.py --help
  python scripts/graph_query.py --vault fixtures/synthetic_vault --query query.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lint_relations_graph import (
    STAGE_GATE_PREDICATES,
    parse_note,
    split_frontmatter,
)

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "v1" / "query" / "graph-dsl.schema.json"

_CANONICAL_URN_PATTERN = re.compile(r"urn:([a-z0-9_-]+):([a-z0-9_-]+):([0-9a-fA-F-]{36})")
_UUID_URN_PATTERN = re.compile(r"^urn:uuid:([0-9a-fA-F-]{36})$")
_WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_TITLE_LINE = re.compile(r"^title:\s*(.*)$", re.MULTILINE)


@dataclass
class Node:
    id: str
    realm: str
    title: str = ""
    path: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    predicate: str
    direction: str = "outbound"
    edge_type: str = "relation"
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


class VaultGraph:
    """In-memory directed multigraph of vault entities and linkages."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        # Outbound edges: source_urn -> list[Edge]
        self.out_edges: Dict[str, List[Edge]] = defaultdict(list)
        # Inbound edges: target_urn -> list[Edge]
        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        # Alias index: maps note slug or secondary URNs to canonical URN
        self.aliases: Dict[str, str] = {}

    def add_node(self, node: Node, aliases: Optional[List[str]] = None) -> None:
        self.nodes[node.id] = node
        self.aliases[node.id] = node.id
        if aliases:
            for alias in aliases:
                self.aliases[alias] = node.id

    def add_edge(self, edge: Edge) -> None:
        self.out_edges[edge.source].append(edge)
        self.in_edges[edge.target].append(edge)

    def resolve_urn(self, identifier: str) -> str:
        return self.aliases.get(identifier, identifier)


def _title_from_frontmatter(frontmatter: str, fallback: str) -> str:
    """Best-effort root `title:` scalar; matches lint_relations_graph unquoting."""
    match = _TITLE_LINE.search(frontmatter)
    if not match:
        return fallback
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value or fallback


def _edge_type_allowed(
    edge: Edge,
    edge_types: Set[str],
    include_wikilinks: bool,
    include_relations: bool,
) -> bool:
    kind = edge.edge_type
    if kind in ("wikilink", "wikilinks") and include_wikilinks is False:
        return False
    if kind in ("relation", "relations") and include_relations is False:
        return False
    if "all" in edge_types:
        return True
    if kind in edge_types:
        return True
    plural = kind if kind.endswith("s") else f"{kind}s"
    singular = kind[:-1] if kind.endswith("s") else kind
    if plural in edge_types or singular in edge_types:
        return True
    if "stage_gates" in edge_types or "stage_gate" in edge_types:
        if kind in ("stage_gate", "stage_gates"):
            return True
        if kind in ("relation", "relations") and edge.predicate in STAGE_GATE_PREDICATES:
            return True
    return False


def load_vault_graph(vault_dir: pathlib.Path) -> VaultGraph:
    """Parse all Markdown notes in vault_dir and construct the directed graph.

    Reuses ``lint_relations_graph.parse_note`` so realm-typed aliases
    (``urn:yeoman:contact:<uuid>``, ``urn:trice:task:<uuid>``,
    ``urn:careen:project:<uuid>``, ...) resolve to the same node as ``$pkm.id``.
    """
    graph = VaultGraph()
    if not vault_dir.exists():
        return graph

    raw_notes: List[Tuple[Node, Any, str]] = []
    for path in sorted(p for p in vault_dir.rglob("*.md") if p.is_file()):
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        record = parse_note(path, vault_dir)
        _fm, body = split_frontmatter(content)
        realm = record.realm or path.parent.name.split("-", 1)[-1]
        node_id = record.pkm_id or f"urn:bosun:{realm}:{path.stem}"
        node = Node(
            id=node_id,
            realm=str(realm),
            title=_title_from_frontmatter(_fm, path.stem),
            path=record.relpath,
            attributes={"relations": dict(record.relations)},
        )
        aliases = list(record.defined_urns) + [path.stem, f"[[{path.stem}]]", path.name]
        graph.add_node(node, aliases=aliases)
        raw_notes.append((node, record, body))

    for node, record, body in raw_notes:
        seen_edges: Set[Tuple[str, str, str]] = set()

        def _add(predicate: str, target: str, edge_type: str) -> None:
            resolved_tgt = graph.resolve_urn(target)
            key = (node.id, resolved_tgt, predicate)
            if key in seen_edges:
                return
            seen_edges.add(key)
            graph.add_edge(
                Edge(
                    source=node.id,
                    target=resolved_tgt,
                    predicate=predicate,
                    direction="outbound",
                    edge_type=edge_type,
                )
            )

        for predicate, targets in record.relations.items():
            for tgt in targets:
                _add(predicate, tgt, "relation")

        for predicate, target in record.stage_gate_edges:
            edge_type = (
                "relation" if predicate in record.relations else "stage_gate"
            )
            _add(predicate, target, edge_type)

        for match in _WIKILINK_PATTERN.finditer(body):
            target_slug = match.group(1).strip()
            resolved_target = graph.resolve_urn(target_slug)
            if resolved_target in graph.nodes:
                _add("wikilink", resolved_target, "wikilink")

    return graph


class GraphQueryEngine:
    """Executes Graph DSL queries against a VaultGraph instance."""

    def __init__(self, graph: VaultGraph) -> None:
        self.graph = graph

    def _candidate_edges(
        self, node_id: str, direction: str
    ) -> List[Tuple[Edge, str]]:
        candidates: List[Tuple[Edge, str]] = []
        if direction in ("outbound", "both", "bidirectional"):
            for edge in self.graph.out_edges.get(node_id, []):
                candidates.append((edge, self.graph.resolve_urn(edge.target)))
        if direction in ("inbound", "both", "bidirectional"):
            for edge in self.graph.in_edges.get(node_id, []):
                in_edge = Edge(
                    source=edge.target,
                    target=edge.source,
                    predicate=edge.predicate,
                    direction="inbound",
                    edge_type=edge.edge_type,
                    weight=edge.weight,
                    properties=edge.properties,
                )
                candidates.append((in_edge, self.graph.resolve_urn(edge.source)))
        return candidates

    def _hop_matches(
        self,
        edge: Edge,
        hop: Dict[str, Any],
        resolved_neighbor: str,
        neighbor_node: Optional[Node],
    ) -> bool:
        if edge.predicate != hop.get("predicate"):
            return False
        if "target" in hop:
            expected = self.graph.resolve_urn(str(hop["target"]))
            if resolved_neighbor != expected:
                return False
        if "target_realm" in hop:
            if (
                neighbor_node is None
                or neighbor_node.realm.lower() != str(hop["target_realm"]).lower()
            ):
                return False
        return True

    def _relation_constraint_matches(
        self,
        edge: Edge,
        resolved_neighbor: str,
        required_relations: Optional[Set[str]],
        required_relation_obj: Optional[Dict[str, Any]],
    ) -> bool:
        """has_relation is an OR of predicates (or one relationFilter) on the edge."""
        if required_relations and edge.predicate not in required_relations:
            return False
        if required_relation_obj:
            return self._hop_matches(
                edge,
                required_relation_obj,
                resolved_neighbor,
                self.graph.nodes.get(resolved_neighbor),
            )
        return True

    def _walk_path(
        self,
        start_nodes: List[str],
        hops: List[Dict[str, Any]],
        *,
        direction: str,
        max_depth: int,
        edge_types: Set[str],
        include_wikilinks: bool,
        include_relations: bool,
        pred_regex: Optional[re.Pattern[str]],
        allowed_realms: Optional[Set[str]],
    ) -> Tuple[Set[str], List[Edge], Dict[str, int]]:
        """Walk an ordered AND of hops. Incomplete paths contribute no nodes."""
        empty: Tuple[Set[str], List[Edge], Dict[str, int]] = (set(), [], {})
        if not hops or max_depth < len(hops):
            return empty

        completed_nodes: Set[str] = set()
        completed_edges: List[Edge] = []
        node_depths: Dict[str, int] = {}
        seen_edge_keys: Set[Tuple[str, str, str, str]] = set()

        def _record(nodes_so_far: List[str], edges_so_far: List[Edge]) -> None:
            for depth, nid in enumerate(nodes_so_far):
                completed_nodes.add(nid)
                prev = node_depths.get(nid)
                if prev is None or depth < prev:
                    node_depths[nid] = depth
            for edge in edges_so_far:
                key = (edge.source, edge.target, edge.predicate, edge.direction)
                if key in seen_edge_keys:
                    continue
                seen_edge_keys.add(key)
                completed_edges.append(edge)

        def dfs(
            node_id: str,
            hop_idx: int,
            nodes_so_far: List[str],
            edges_so_far: List[Edge],
        ) -> None:
            if hop_idx == len(hops):
                _record(nodes_so_far, edges_so_far)
                return
            hop = hops[hop_idx]
            for edge, neighbor_id in self._candidate_edges(node_id, direction):
                if not _edge_type_allowed(
                    edge, edge_types, include_wikilinks, include_relations
                ):
                    continue
                if pred_regex and not pred_regex.search(edge.predicate):
                    continue
                neighbor_node = self.graph.nodes.get(neighbor_id)
                if allowed_realms and neighbor_node:
                    if neighbor_node.realm.lower() not in allowed_realms:
                        continue
                if not self._hop_matches(edge, hop, neighbor_id, neighbor_node):
                    continue
                dfs(
                    neighbor_id,
                    hop_idx + 1,
                    nodes_so_far + [neighbor_id],
                    edges_so_far + [edge],
                )

        for root in start_nodes:
            if root in self.graph.nodes:
                dfs(root, 0, [root], [])
        return completed_nodes, completed_edges, node_depths

    def execute(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a graph query dictionary and return projected results."""
        start_time = time.perf_counter()

        # Extract filters from top-level shortcuts and/or explicit filters block
        filters = query.get("filters", {})
        if not isinstance(filters, dict):
            filters = {}

        # Resolve linked_from root nodes
        linked_from = query.get("linked_from") or filters.get("linked_from")
        start_nodes: List[str] = []
        if isinstance(linked_from, str):
            start_nodes = [self.graph.resolve_urn(linked_from)]
        elif isinstance(linked_from, list):
            start_nodes = [self.graph.resolve_urn(str(u)) for u in linked_from]

        # If no starting nodes are specified, discover candidate roots
        match_realm = query.get("match_realm") or filters.get("match_realm")
        allowed_realms: Optional[Set[str]] = None
        if isinstance(match_realm, str):
            allowed_realms = {match_realm.lower()}
        elif isinstance(match_realm, list):
            allowed_realms = {str(r).lower() for r in match_realm}

        has_relation = query.get("has_relation") or filters.get("has_relation")
        required_relations: Optional[Set[str]] = None
        required_relation_obj: Optional[Dict[str, Any]] = None
        if isinstance(has_relation, str):
            required_relations = {has_relation}
        elif isinstance(has_relation, list):
            required_relations = {str(r) for r in has_relation}
        elif isinstance(has_relation, dict):
            required_relation_obj = has_relation

        predicate_pattern_str = query.get("predicate_pattern") or filters.get("predicate_pattern")
        pred_regex = re.compile(predicate_pattern_str) if predicate_pattern_str else None

        direction = query.get("direction", "outbound").lower()
        max_depth = query.get("max_depth", filters.get("max_depth", 1))
        edge_types = set(query.get("edge_types", ["relations", "wikilinks"]))
        include_wikilinks = filters.get("include_wikilinks", True)
        include_relations = filters.get("include_relations", True)

        path_hops = query.get("path") or filters.get("path")
        if not isinstance(path_hops, list) or not path_hops:
            path_hops = None

        projections = query.get("projections", ["nodes", "edges"])
        limit = query.get("limit")

        target_node_raw = query.get("target_node") or filters.get("target_node")
        target_node = self.graph.resolve_urn(str(target_node_raw)) if target_node_raw else None

        # Determine seeds
        if not start_nodes:
            # All graph nodes matching initial realm filter
            for node_id, node in self.graph.nodes.items():
                if allowed_realms and node.realm.lower() not in allowed_realms:
                    continue
                start_nodes.append(node_id)

        visited_nodes: Set[str] = set()
        traversed_edges: List[Edge] = []
        node_depths: Dict[str, int] = {}
        parent_map: Dict[str, str] = {}

        if path_hops:
            visited_nodes, traversed_edges, node_depths = self._walk_path(
                start_nodes,
                path_hops,
                direction=direction,
                max_depth=max_depth,
                edge_types=edge_types,
                include_wikilinks=bool(include_wikilinks),
                include_relations=bool(include_relations),
                pred_regex=pred_regex,
                allowed_realms=allowed_realms,
            )
        else:
            queue: deque[Tuple[str, int]] = deque()
            for root in start_nodes:
                if root in self.graph.nodes:
                    visited_nodes.add(root)
                    node_depths[root] = 0
                    queue.append((root, 0))

            target_found = False
            while queue:
                current_id, depth = queue.popleft()
                if depth >= max_depth:
                    continue

                for edge, neighbor_id in self._candidate_edges(current_id, direction):
                    if not _edge_type_allowed(
                        edge, edge_types, bool(include_wikilinks), bool(include_relations)
                    ):
                        continue

                    if pred_regex and not pred_regex.search(edge.predicate):
                        continue

                    neighbor_node = self.graph.nodes.get(neighbor_id)
                    if neighbor_node and allowed_realms:
                        if neighbor_node.realm.lower() not in allowed_realms:
                            continue

                    if not self._relation_constraint_matches(
                        edge,
                        neighbor_id,
                        required_relations,
                        required_relation_obj,
                    ):
                        continue

                    traversed_edges.append(edge)
                    if neighbor_id not in visited_nodes:
                        visited_nodes.add(neighbor_id)
                        parent_map[neighbor_id] = current_id
                        node_depths[neighbor_id] = depth + 1
                        queue.append((neighbor_id, depth + 1))
                        if target_node and neighbor_id == target_node:
                            target_found = True
                            break
                if target_found:
                    break

        # Build Projection Results
        result: Dict[str, Any] = {
            "projections": projections,
        }
        if query.get("query_id"):
            result["query_id"] = query["query_id"]

        # If target_node was requested or shortest_path in projections, compute shortest_path
        if target_node or "shortest_path" in projections:
            if target_node and target_node in parent_map:
                sp: List[str] = [target_node]
                curr = target_node
                while curr in parent_map:
                    curr = parent_map[curr]
                    sp.append(curr)
                sp.reverse()
                result["shortest_path"] = sp
            elif target_node and target_node in start_nodes:
                result["shortest_path"] = [target_node]
            else:
                result["shortest_path"] = []

        # Collect and project nodes
        ordered_node_ids = sorted(visited_nodes)
        if limit and len(ordered_node_ids) > limit:
            ordered_node_ids = ordered_node_ids[:limit]

        if "nodes" in projections:
            projected_nodes = []
            for nid in ordered_node_ids:
                node = self.graph.nodes.get(nid)
                if node:
                    pnode: Dict[str, Any] = {
                        "id": node.id,
                        "realm": node.realm,
                        "title": node.title,
                        "path": node.path,
                        "depth": node_depths.get(nid, 0),
                    }
                    if node.attributes:
                        pnode["attributes"] = node.attributes
                    projected_nodes.append(pnode)
                else:
                    projected_nodes.append({
                        "id": nid,
                        "realm": "external",
                        "depth": node_depths.get(nid, 0),
                    })
            result["nodes"] = projected_nodes

        # Collect and project edges
        if "edges" in projections:
            projected_edges = []
            for edge in traversed_edges:
                if edge.source in visited_nodes and edge.target in visited_nodes:
                    projected_edges.append({
                        "source": edge.source,
                        "target": edge.target,
                        "predicate": edge.predicate,
                        "direction": edge.direction,
                        "edge_type": edge.edge_type,
                        "weight": edge.weight,
                    })
            if limit and len(projected_edges) > limit:
                projected_edges = projected_edges[:limit]
            result["edges"] = projected_edges

        # Collect and project Subgraph Adjacency Matrix
        if "subgraph_adjacency_matrix" in projections:
            n = len(ordered_node_ids)
            node_index = {nid: idx for idx, nid in enumerate(ordered_node_ids)}
            matrix = [[0.0 for _ in range(n)] for _ in range(n)]

            for edge in traversed_edges:
                src_idx = node_index.get(edge.source)
                tgt_idx = node_index.get(edge.target)
                if src_idx is not None and tgt_idx is not None:
                    matrix[src_idx][tgt_idx] += edge.weight

            result["subgraph_adjacency_matrix"] = {
                "nodes": ordered_node_ids,
                "matrix": matrix,
                "dimension": n,
                "directed": True,
            }

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        result["metrics"] = {
            "node_count": len(ordered_node_ids),
            "edge_count": len(traversed_edges),
            "traversal_depth": max(node_depths.values()) if node_depths else 0,
            "execution_time_ms": round(elapsed_ms, 3),
        }

        return result

    def find_shortest_path(
        self,
        source_urn: str,
        target_urn: str,
        max_depth: int = 100
    ) -> Optional[List[str]]:
        """Compute the shortest path sequence of node URNs from source to target."""
        src = self.graph.resolve_urn(source_urn)
        tgt = self.graph.resolve_urn(target_urn)
        if src == tgt:
            return [src]

        visited: Set[str] = {src}
        parent: Dict[str, str] = {}
        queue: deque[Tuple[str, int]] = deque([(src, 0)])

        while queue:
            curr, d = queue.popleft()
            if d >= max_depth:
                continue
            for edge in self.graph.out_edges.get(curr, []):
                nxt = edge.target
                if nxt not in visited:
                    visited.add(nxt)
                    parent[nxt] = curr
                    if nxt == tgt:
                        # Reconstruct path
                        path = [tgt]
                        c = tgt
                        while c in parent:
                            c = parent[c]
                            path.append(c)
                        path.reverse()
                        return path
                    queue.append((nxt, d + 1))
        return None

    def execute_result_contract(
        self,
        query: Dict[str, Any],
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute query and format output strictly conforming to graph-result.schema.json."""
        if not query_id:
            query_id = query.get("query_id")
        if not query_id:
            # Generate deterministic/UUID string for execution ID
            query_id = f"018f3a00-0000-7000-8000-{int(time.time() * 1000) % 1000000000000:012d}"

        # Ensure nodes and edges are projected
        projections = list(query.get("projections", ["nodes", "edges"]))
        if "nodes" not in projections:
            projections.append("nodes")
        if "edges" not in projections:
            projections.append("edges")

        query_copy = dict(query)
        query_copy["projections"] = projections
        query_copy["query_id"] = query_id

        raw_result = self.execute(query_copy)
        metrics = raw_result.get("metrics", {})

        payload: Dict[str, Any] = {
            "query_id": query_id,
            "matched_nodes": raw_result.get("nodes", []),
            "resolved_edges": raw_result.get("edges", []),
            "depth_reached": metrics.get("traversal_depth", 0),
            "execution_duration_ms": metrics.get("execution_time_ms", 0.0),
        }

        if "subgraph_adjacency_matrix" in query.get("projections", []):
            if "subgraph_adjacency_matrix" in raw_result:
                payload["subgraph_adjacency_matrix"] = raw_result["subgraph_adjacency_matrix"]

        if "shortest_path" in raw_result and raw_result["shortest_path"]:
            payload["shortest_path"] = raw_result["shortest_path"]

        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Vault Graph Query Engine")
    parser.add_argument("--vault", type=pathlib.Path, default=_REPO_ROOT / "fixtures" / "synthetic_vault")
    parser.add_argument("--query", type=pathlib.Path, help="JSON file containing graph query")
    parser.add_argument("--linked-from", type=str, help="Starting node URN")
    parser.add_argument("--realm", type=str, help="Filter by realm")
    parser.add_argument("--max-depth", type=int, default=2)
    args = parser.parse_args()

    graph = load_vault_graph(args.vault)
    engine = GraphQueryEngine(graph)

    query_payload: Dict[str, Any] = {
        "projections": ["nodes", "edges", "subgraph_adjacency_matrix"],
        "max_depth": args.max_depth,
    }
    if args.linked_from:
        query_payload["linked_from"] = args.linked_from
    if args.realm:
        query_payload["match_realm"] = args.realm
    if args.query and args.query.exists():
        with open(args.query, encoding="utf-8") as fh:
            query_payload = json.load(fh)

    result = engine.execute(query_payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
