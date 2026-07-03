"""Export graph as Mermaid diagram."""

from pathlib import Path
from typing import Dict, List


def export_mermaid(graph_data: Dict, output_path: Path) -> Path:
    """Export graph as Mermaid flowchart."""
    entities = {e["id"]: e for e in graph_data.get("entities", [])}
    relationships = graph_data.get("relationships", [])
    clusters = graph_data.get("clusters", [])
    god_nodes = [g["id"] for g in graph_data.get("metadata", {}).get("god_nodes", [])]

    lines = ["graph TB"]

    type_styles = {
        "module": ":::module",
        "class": ":::class",
        "function": ":::function",
        "route": ":::route",
        "schema": ":::schema",
        "config": ":::config",
    }

    node_map = {}
    node_counter = [0]

    def safe_id(name: str) -> str:
        if name not in node_map:
            node_counter[0] += 1
            node_map[name] = f"N{node_counter[0]}"
        return node_map[name]

    # Group entities by file for subgraphs
    file_groups: Dict[str, List[str]] = {}
    for eid, ent in entities.items():
        f = ent.get("file", "unknown")
        parts = f.split("/")
        group = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
        if group not in file_groups:
            file_groups[group] = []
        file_groups[group].append(eid)

    # Create subgraphs for clusters
    for cluster in clusters:
        cid = safe_id(cluster["id"])
        lines.append(f'    subgraph {cid}["{cluster["name"]}"]')
        for member in cluster["members"]:
            if member in entities:
                nid = safe_id(member)
                ent = entities[member]
                style = type_styles.get(ent["type"], "")
                god_mark = " ⭐" if member in god_nodes else ""
                label = ent["name"].replace('"', "'")
                lines.append(f'        {nid}["{label}{god_mark}"]{style}')
        lines.append("    end")

    # Add entities not in any cluster
    clustered = set()
    for cluster in clusters:
        clustered.update(cluster["members"])

    for eid, ent in entities.items():
        if eid not in clustered:
            nid = safe_id(eid)
            style = type_styles.get(ent["type"], "")
            god_mark = " ⭐" if eid in god_nodes else ""
            label = ent["name"].replace('"', "'")
            lines.append(f'    {nid}["{label}{god_mark}"]{style}')

    # Add edges
    for rel in relationships:
        if rel["source"] in node_map and rel["target"] in node_map:
            src = node_map[rel["source"]]
            tgt = node_map[rel["target"]]
            label = rel["type"].replace('"', "'")
            lines.append(f'    {src} -->|"{label}"| {tgt}')

    # Add styles
    lines.extend([
        "",
        "    classDef module fill:#1f6feb,stroke:#58a6ff,color:#fff",
        "    classDef class fill:#238636,stroke:#3fb950,color:#fff",
        "    classDef function fill:#8957e5,stroke:#d2a8ff,color:#fff",
        "    classDef route fill:#9e6a03,stroke:#f0883e,color:#fff",
        "    classDef schema fill:#bf3989,stroke:#f778ba,color:#fff",
        "    classDef config fill:#484f58,stroke:#8b949e,color:#fff",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path
