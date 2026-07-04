"""Community detection and graph analysis."""

from collections import defaultdict
from pathlib import Path

try:
    import networkx as nx
except ImportError:
    nx = None


def detect_communities(G: "nx.DiGraph") -> dict[str, list[str]]:
    """Detect communities using Leiden algorithm (falls back to greedy modularity).

    Uses the undirected version of G for modularity-based algorithms since
    directed edges with no reciprocation produce degenerate partitions.
    Falls back to file-path-based clustering when the graph is too sparse
    for modularity methods (e.g. monorepos with isolated packages).
    """
    if nx is None:
        return {}

    # --- Attempt 1: Leiden algorithm (best quality) ---
    try:
        import igraph as ig
        from leidenalg import ModularityVertexPartition, find_partition
        g = ig.Graph.from_networkx(G.to_undirected())
        partition = find_partition(g, ModularityVertexPartition)
        communities = defaultdict(list)
        for node_idx, comm_id in enumerate(partition.membership):
            node = list(G.nodes())[node_idx]
            communities[f"community_{comm_id}"].append(node)
        # Filter out singleton communities (noise)
        return {k: v for k, v in communities.items() if len(v) > 1}
    except ImportError:
        pass
    except Exception:
        pass

    # --- Attempt 2: Greedy modularity (on undirected graph) ---
    try:
        from networkx.algorithms.community import greedy_modularity_communities
        G_undir = G.to_undirected()
        communities = greedy_modularity_communities(G_undir)
        result = {}
        for i, comm in enumerate(communities):
            if len(comm) > 1:  # skip singletons
                result[f"community_{i}"] = list(comm)
        if result:
            return result
    except Exception:
        pass

    # --- Attempt 3: File-path-based clustering (always works) ---
    return _path_based_communities(G)


def _path_based_communities(G: "nx.DiGraph") -> dict[str, list[str]]:
    """Group entities by their top-level directory/module path.

    This is the fallback for sparse or disconnected graphs where
    modularity-based methods produce only singletons.  Every monorepo
    has a natural directory structure that maps to logical modules.
    """
    groups = defaultdict(list)
    for node in G.nodes():
        data = G.nodes[node]
        filepath = data.get("file", "")
        parts = Path(filepath).parts
        # Build a module key from the first 2-3 meaningful path segments
        if len(parts) >= 3:
            # e.g. "packages/core/lib/genui/..." → "packages/core"
            key = "/".join(parts[:2])
        elif len(parts) >= 2:
            key = "/".join(parts[:2])
        elif parts:
            key = parts[0]
        else:
            key = "root"
        groups[key].append(node)

    # Only keep groups with 2+ members
    return {k: v for k, v in groups.items() if len(v) > 1}


def _community_display_name(comm_id: str, members: list[str], G: "nx.DiGraph") -> str:
    """Generate a human-readable name for a community based on its dominant file paths."""
    if not comm_id.startswith("community_"):
        # Path-based key like "packages/core" — use as-is
        return comm_id

    # For algorithmic communities, find the most common directory prefix
    dir_counts: dict[str, int] = defaultdict(int)
    subdir_counts: dict[str, int] = defaultdict(int)
    for node in members:
        data = G.nodes.get(node, {})
        filepath = data.get("file", "")
        parts = Path(filepath).parts
        if len(parts) >= 3:
            prefix = "/".join(parts[:2])
            subdir = parts[2] if len(parts) > 2 else ""
        elif len(parts) >= 2:
            prefix = "/".join(parts[:2])
            subdir = ""
        elif parts:
            prefix = parts[0]
            subdir = ""
        else:
            prefix = "other"
            subdir = ""
        dir_counts[prefix] += 1
        if subdir:
            subdir_counts[subdir] += 1

    if dir_counts:
        dominant = max(dir_counts, key=dir_counts.get)
        short = dominant.split("/")[-1]
        # Add subdir hint if there's a clear dominant subdirectory
        if subdir_counts:
            top_subdir = max(subdir_counts, key=subdir_counts.get)
            if subdir_counts[top_subdir] > len(members) * 0.3:
                return f"{short}/{top_subdir}"
        return short
    return f"Community {comm_id.split('_', 1)[1]}"


def _get_module_key(filepath: str) -> str:
    """Extract a module key from a file path (e.g. 'packages/core')."""
    parts = Path(filepath).parts
    if len(parts) >= 3:
        return "/".join(parts[:2])
    elif len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0] if parts else "root"


def find_surprising_links(
    G: "nx.DiGraph",
    entities: dict,
    min_path_length: int = 4,
) -> list[dict]:
    """Find cross-module connections that are genuinely unexpected.

    In a monorepo, cross-*package* imports are normal (core → user_app).
    Surprising links are:
      - Same-file reverse dependencies (A imports B AND B imports A)
      - Test files importing implementation details (not just public API)
      - Deep cross-package calls (e.g. UI layer calling DB internals directly)
    """
    surprising = []

    # 1. Find circular dependencies (A→B and B→A)
    for source, target in G.edges():
        if G.has_edge(target, source) and source < target:  # deduplicate
            surprising.append({
                "source": source,
                "target": target,
                "reason": f"Circular dependency: {source} ↔ {target}",
            })

    # 2. Find test files importing non-public implementation details
    for source, target in G.edges():
        src_ent = entities.get(source)
        tgt_ent = entities.get(target)
        if not src_ent or not tgt_ent:
            continue
        if "/test/" in src_ent.file and "/lib/" in tgt_ent.file:
            edge_type = G.edges[source, target].get("type", "")
            if edge_type == "imports":
                # Check if target is in an internal/private directory
                if any(seg.startswith("_") for seg in Path(tgt_ent.file).parts):
                    surprising.append({
                        "source": source,
                        "target": target,
                        "reason": f"Test imports private implementation: {src_ent.file} → {tgt_ent.file}",
                    })

    # 3. Find cross-package extends/implements (UI layer extending core internals)
    for source, target in G.edges():
        src_ent = entities.get(source)
        tgt_ent = entities.get(target)
        if not src_ent or not tgt_ent:
            continue
        src_mod = _get_module_key(src_ent.file)
        tgt_mod = _get_module_key(tgt_ent.file)
        if src_mod != tgt_mod:
            edge_data = G.edges[source, target]
            rel_type = edge_data.get("type", "")
            if rel_type in ("extends", "implements"):
                surprising.append({
                    "source": source,
                    "target": target,
                    "reason": f"Cross-package {rel_type}: {src_ent.file} → {tgt_ent.file}",
                })

    return surprising[:20]


def find_god_nodes(G: "nx.DiGraph", top_n: int = 10) -> list[dict]:
    """Find nodes with highest degree centrality."""
    degree = dict(G.degree())
    sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:top_n]

    result = []
    for node_id, deg in sorted_nodes:
        node_data = G.nodes.get(node_id, {})
        result.append({
            "id": node_id,
            "name": node_data.get("name", node_id),
            "connections": deg,
            "reason": f"High connectivity ({deg} edges) in {node_data.get('file', 'unknown')}",
        })
    return result


def find_paths(
    G: "nx.DiGraph", source: str, target: str, max_length: int = 6
) -> list[list[str]]:
    """Find all paths between source and target up to max_length."""
    if source not in G or target not in G:
        return []

    try:
        paths = list(nx.all_simple_paths(G, source, target, cutoff=max_length))
        return paths[:10]
    except Exception:
        return []


def get_entity_context(
    entity_id: str, G: "nx.DiGraph", entities: dict
) -> dict:
    """Get full context for an entity."""
    if entity_id not in G:
        return {"error": f"Entity '{entity_id}' not found"}

    node_data = G.nodes[entity_id]
    predecessors = list(G.predecessors(entity_id))
    successors = list(G.successors(entity_id))

    incoming = []
    for pred in predecessors:
        edge_data = G.edges[pred, entity_id]
        incoming.append({
            "from": pred,
            "type": edge_data.get("type", "unknown"),
            "confidence": edge_data.get("confidence", "UNKNOWN"),
        })

    outgoing = []
    for succ in successors:
        edge_data = G.edges[entity_id, succ]
        outgoing.append({
            "to": succ,
            "type": edge_data.get("type", "unknown"),
            "confidence": edge_data.get("confidence", "UNKNOWN"),
        })

    return {
        "id": entity_id,
        "name": node_data.get("name", entity_id),
        "type": node_data.get("type", "unknown"),
        "file": node_data.get("file", "unknown"),
        "line": node_data.get("line", 0),
        "metadata": {k: v for k, v in node_data.items() if k not in ("name", "type", "file", "line")},
        "incoming_relationships": incoming,
        "outgoing_relationships": outgoing,
        "total_connections": len(predecessors) + len(successors),
    }
