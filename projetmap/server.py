"""Projetmap MCP Server — Knowledge graph as a service for AI agents.

Exposes Projetmap's codebase analysis capabilities as MCP tools that any
IDE agent (Cursor, Windsurf, ZCode, Claude Desktop) can call natively.

Usage:
    python -m projetmap mcp          # Start MCP server over stdio
    python -m projetmap mcp --help   # Show server options
"""
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "projetmap",
    instructions=(
        "Knowledge graph generator for codebases. "
        "Scan projects to get structural analysis, dead code detection, "
        "state mutation hotspots, listener health, and architectural insights."
    ),
)

# In-memory cache: path -> graph_data
_graph_cache: dict = {}


def _get_out_dir(path: str) -> Path:
    """Get the .projetmap output directory for a project."""
    return Path(path) / ".projetmap"


def _load_graph(path: str) -> dict | None:
    """Load cached graph from disk or memory."""
    if path in _graph_cache:
        return _graph_cache[path]

    out = _get_out_dir(path)
    graph_file = out / "graph.json"
    if not graph_file.exists():
        return None

    with open(graph_file) as f:
        data = json.load(f)
    _graph_cache[path] = data
    return data


def _load_behavioral(path: str) -> dict | None:
    """Load behavioral analysis from disk."""
    out = _get_out_dir(path)
    bh_file = out / "behavioral_analysis.json"
    if not bh_file.exists():
        return None
    with open(bh_file) as f:
        return json.load(f)


# ── Tools ──────────────────────────────────────────────────────────────


@mcp.tool()
def projetmap_scan(path: str, refresh: bool = False, behavioral: bool = False) -> str:
    """Scan a codebase and build a knowledge graph.

    Run this first to initialize the graph for a project.
    Subsequent tool calls use the cached graph.

    Args:
        path: Absolute path to the project root.
        refresh: Force re-scan even if cache exists.
        behavioral: Also run behavioral analysis (dead code, state flow).
    """
    from projetmap.cli import run_behavioral_analysis_pipeline, run_pipeline

    try:
        graph_data = run_pipeline(
            target=path,
            refresh=refresh,
            output_dir=".projetmap",
        )
        _graph_cache[path] = graph_data

        meta = graph_data.get("metadata", {})
        result = {
            "status": "ok",
            "entities": meta.get("entity_count", 0),
            "relationships": meta.get("relationship_count", 0),
            "clusters": len(graph_data.get("clusters", [])),
            "project": meta.get("project", {}),
        }

        if behavioral:
            bh = run_behavioral_analysis_pipeline(
                target=path,
                graph_data=graph_data,
                output_dir=".projetmap",
            )
            summary = bh.get("summary", {})
            result["behavioral"] = {
                "dead_code": summary.get("dead_functions", 0),
                "hot_paths": summary.get("hot_paths", 0),
                "state_mutations": summary.get("total_state_mutations", 0),
                "unpaired_listeners": summary.get("unpaired_listeners", 0),
            }

        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
def projetmap_report(path: str) -> str:
    """Get the full Markdown report for a scanned codebase.

    Args:
        path: Absolute path to the project root.
    """
    out = _get_out_dir(path)
    report_file = out / "GRAPH_REPORT.md"
    if not report_file.exists():
        return json.dumps({
            "status": "error",
            "error": f"No report found at {report_file}. Run projetmap_scan first.",
        })
    return report_file.read_text(encoding="utf-8")


@mcp.tool()
def projetmap_query(path: str, entity_name: str) -> str:
    """Query a specific entity by name. Returns details and relationships.

    Args:
        path: Absolute path to the project root.
        entity_name: Name or partial name to search for (case-insensitive).
    """
    data = _load_graph(path)
    if not data:
        return json.dumps({
            "status": "error",
            "error": "No cached graph. Run projetmap_scan first.",
        })

    entities = {e["id"]: e for e in data.get("entities", [])}
    relationships = data.get("relationships", [])

    matches = []
    for eid, ent in entities.items():
        if (entity_name.lower() in eid.lower()
                or entity_name.lower() in ent.get("name", "").lower()):
            matches.append((eid, ent))

    if not matches:
        return json.dumps({"status": "not_found", "query": entity_name})

    results = []
    for eid, ent in matches[:5]:
        incoming = [r for r in relationships if r["target"] == eid]
        outgoing = [r for r in relationships if r["source"] == eid]
        results.append({
            "id": eid,
            "name": ent.get("name", ""),
            "type": ent.get("type", ""),
            "file": ent.get("file", ""),
            "line": ent.get("line"),
            "incoming": [{"source": r["source"], "type": r["type"]} for r in incoming[:10]],
            "outgoing": [{"target": r["target"], "type": r["type"]} for r in outgoing[:10]],
        })

    return json.dumps({"status": "ok", "matches": results}, indent=2)


@mcp.tool()
def projetmap_path(path: str, source: str, dest: str) -> str:
    """Find the dependency path between two entities.

    Args:
        path: Absolute path to the project root.
        source: Source entity name (partial match).
        dest: Destination entity name (partial match).
    """
    data = _load_graph(path)
    if not data:
        return json.dumps({
            "status": "error",
            "error": "No cached graph. Run projetmap_scan first.",
        })

    import networkx as nx
    G = nx.DiGraph()
    for r in data.get("relationships", []):
        G.add_edge(r["source"], r["target"], type=r["type"])

    # Search entities by name, then map to file paths for graph lookup
    entities = data.get("entities", [])

    def _find_nodes(query: str) -> list:
        """Find graph nodes matching a query (by entity name or file path)."""
        # Direct file path match
        direct = [n for n in G.nodes() if query.lower() in n.lower()]
        if direct:
            return direct
        # Entity name -> file path
        matches = [
            e["file"] for e in entities
            if query.lower() in e.get("name", "").lower()
            or query.lower() in e.get("id", "").lower()
        ]
        return list(set(matches))

    source_nodes = _find_nodes(source)
    dest_nodes = _find_nodes(dest)

    if not source_nodes:
        return json.dumps({"status": "not_found", "entity": source})
    if not dest_nodes:
        return json.dumps({"status": "not_found", "entity": dest})

    paths_found = []
    for s in source_nodes[:3]:
        for d in dest_nodes[:3]:
            try:
                paths = list(nx.all_simple_paths(G, s, d, cutoff=8))
                for p in paths[:3]:
                    paths_found.append({"from": s, "to": d, "path": p})
            except Exception:
                pass

    if not paths_found:
        return json.dumps({"status": "no_path", "from": source, "to": dest})

    return json.dumps({"status": "ok", "paths": paths_found}, indent=2)


@mcp.tool()
def projetmap_dead_code(path: str) -> str:
    """Get dead code — functions unreachable from entry points.

    Args:
        path: Absolute path to the project root.
    """
    bh = _load_behavioral(path)
    if not bh:
        return json.dumps({
            "status": "error",
            "error": "No behavioral analysis. Run projetmap_scan with behavioral=true.",
        })

    dead = bh.get("dead_code", [])
    return json.dumps({
        "status": "ok",
        "count": len(dead),
        "functions": dead[:30],
    }, indent=2)


@mcp.tool()
def projetmap_hotspots(path: str) -> str:
    """Get state mutation hotspots — classes with the most state changes.

    High mutation counts indicate potential architectural risk.

    Args:
        path: Absolute path to the project root.
    """
    bh = _load_behavioral(path)
    if not bh:
        return json.dumps({
            "status": "error",
            "error": "No behavioral analysis. Run projetmap_scan with behavioral=true.",
        })

    hotspots = bh.get("mutation_hotspots", [])
    return json.dumps({
        "status": "ok",
        "count": len(hotspots),
        "hotspots": hotspots[:15],
    }, indent=2)


@mcp.tool()
def projetmap_listeners(path: str) -> str:
    """Get unpaired listener warnings — potential memory leaks.

    Components that add listeners without removing them may leak memory.

    Args:
        path: Absolute path to the project root.
    """
    bh = _load_behavioral(path)
    if not bh:
        return json.dumps({
            "status": "error",
            "error": "No behavioral analysis. Run projetmap_scan with behavioral=true.",
        })

    unpaired = bh.get("unpaired_listeners", [])
    problematic = [u for u in unpaired if u.get("unpaired", 0) > 0]
    paired = [u for u in unpaired if u.get("unpaired", 0) == 0]

    return json.dumps({
        "status": "ok",
        "problematic_count": len(problematic),
        "paired_count": len(paired),
        "problematic": problematic,
    }, indent=2)


@mcp.tool()
def projetmap_god_nodes(path: str) -> str:
    """Get god nodes — most-connected modules (architectural bottlenecks).

    These modules have the highest degree centrality and may indicate
    areas that need refactoring.

    Args:
        path: Absolute path to the project root.
    """
    data = _load_graph(path)
    if not data:
        return json.dumps({
            "status": "error",
            "error": "No cached graph. Run projetmap_scan first.",
        })

    god_nodes = data.get("metadata", {}).get("god_nodes", data.get("god_nodes", []))
    return json.dumps({
        "status": "ok",
        "count": len(god_nodes),
        "god_nodes": god_nodes[:10],
    }, indent=2)


# ── Entry point ────────────────────────────────────────────────────────


def main():
    """Run the Projetmap MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
