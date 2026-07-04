"""Export graph as human-readable Markdown report."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path


def export_report(graph_data: dict, output_path: Path) -> Path:
    """Export GRAPH_REPORT.md."""
    project = graph_data.get("project", {})
    entities = graph_data.get("entities", [])
    relationships = graph_data.get("relationships", [])
    clusters = graph_data.get("clusters", [])
    metadata = graph_data.get("metadata", {})
    god_nodes = metadata.get("god_nodes", [])
    surprising_links = metadata.get("surprising_links", [])

    name = project.get("name", "Unknown")
    lang = project.get("language", "Unknown")
    framework = project.get("framework", "Unknown")
    files_analyzed = project.get("files_analyzed", 0)

    entity_count = len(entities)
    rel_count = len(relationships)
    cluster_count = len(clusters)

    # Count confidence levels
    confidence = defaultdict(int)
    for r in relationships:
        confidence[r.get("confidence", "UNKNOWN")] += 1

    # Count entity types
    entity_types = defaultdict(int)
    for e in entities:
        entity_types[e.get("type", "unknown")] += 1

    lines = [
        f"# 🕸️ {name} — Knowledge Graph Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d')} | **Generator**: Codemap v1.0",
        "",
        "---",
        "",
        "## Overview",
        "",
        "| Attribute | Value |",
        "|-----------|-------|",
        f"| **Project** | {name} |",
        f"| **Language** | {lang} |",
        f"| **Framework** | {framework} |",
        f"| **Files analyzed** | {files_analyzed} |",
        f"| **Entities** | {entity_count} |",
        f"| **Relationships** | {rel_count} |",
        f"| **Clusters** | {cluster_count} |",
        "",
    ]

    # Entity type breakdown
    if entity_types:
        lines.extend([
            "### Entity Types",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for etype, count in sorted(entity_types.items(), key=lambda x: -x[1]):
            lines.append(f"| {etype} | {count} |")
        lines.append("")

    # God Nodes
    if god_nodes:
        lines.extend([
            "## God Nodes (Highest Connectivity)",
            "",
        ])
        for i, gn in enumerate(god_nodes[:10], 1):
            node_id = gn.get("id", gn.get("name", "?"))
            connections = gn.get("connections", 0)
            lines.append(
                f"### {i}. `{node_id}` — {connections} connections ⭐"
            )
            reason = gn.get("reason", "High connectivity")
            lines.append(f"**Role**: {reason}")
            lines.append("")

    # Surprising Links
    if surprising_links:
        lines.extend([
            "## Surprising Cross-Module Links ⚡",
            "",
        ])
        for i, link in enumerate(surprising_links[:10], 1):
            lines.append(f"### {i}. `{link['source']}` → `{link['target']}`")
            lines.append(f"{link.get('reason', 'Unexpected cross-module connection')}")
            lines.append("")

    # Clusters — filter singletons and show top communities by size
    meaningful_clusters = [
        c for c in clusters
        if len(c.get("members", [])) > 1
    ]
    if meaningful_clusters:
        # Sort by size descending
        meaningful_clusters.sort(key=lambda c: len(c.get("members", [])), reverse=True)
        lines.extend([
            "## Cluster Map",
            "",
            f"*{len(meaningful_clusters)} communities detected (singletons filtered out)*",
            "",
            "| # | Cluster | Members | Top Entities |",
            "|---|---------|---------|--------------|",
        ])
        for i, cluster in enumerate(meaningful_clusters[:25], 1):
            members = cluster.get("members", [])
            member_count = len(members)
            # Show first 3 member names as a preview
            preview = ", ".join(members[:3])
            if member_count > 3:
                preview += f" +{member_count - 3} more"
            lines.append(
                f"| {i} | {cluster['name']} | {member_count} | {preview[:70]} |"
            )
        lines.append("")

    # Dependency overview
    lines.extend([
        "## Dependency Graph",
        "",
        "### Module-Level Dependencies",
        "",
        "```",
    ])

    # Build a simple dependency graph from relationships
    module_deps = defaultdict(set)
    for rel in relationships:
        if rel["type"] == "imports":
            module_deps[rel["source"]].add(rel["target"])

    for source in sorted(module_deps.keys())[:20]:
        targets = sorted(module_deps[source])[:5]
        lines.append(f"  {source} → {', '.join(targets)}")
    lines.extend(["```", ""])

    # Confidence Report
    lines.extend([
        "## Confidence Report",
        "",
        "| Level | Count | Meaning |",
        "|-------|-------|---------|",
        f"| **EXTRACTED** | {confidence.get('EXTRACTED', 0)} | Directly observed in source |",
        f"| **INFERRED** | {confidence.get('INFERRED', 0)} | Deduced from patterns |",
        f"| **AMBIGUOUS** | {confidence.get('AMBIGUOUS', 0)} | Uncertain connections |",
        "",
    ])

    # Suggested questions
    lines.extend([
        "## Suggested Exploration Questions",
        "",
        "1. What are the most central modules and why?",
        "2. Are there circular dependencies between packages?",
        "3. Which modules have the most incoming dependencies (stable)?",
        "4. Which modules depend on the most others (unstable)?",
        "5. Are there surprising cross-module connections worth investigating?",
        "",
        "---",
        "",
        f"*Generated by Codemap v1.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path
