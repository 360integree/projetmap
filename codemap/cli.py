#!/usr/bin/env python3
"""
Codemap — Knowledge graph generator for codebases.

Turns any folder of code, docs, and configs into a queryable knowledge graph.
Outputs: graph.json, GRAPH_REPORT.md, graph.html, graph.mermaid

Usage:
    python -m codemap <path>                    # Full pipeline
    python -m codemap <path> --report           # Just the report
    python -m codemap <path> --json             # Just JSON
    python -m codemap <path> --html             # Just interactive HTML
    python -m codemap <path> --mermaid          # Just Mermaid diagram
    python -m codemap <path> --refresh          # Force re-scan
    python -m codemap <path> --query <entity>   # Query an entity
    python -m codemap <path> --path A B         # Find path between entities
    python -m codemap <path> --scan-dirs lib apps  # Scan specific dirs
    python -m codemap <path> --analyze-prompts  # Analyze instruction files for redundancies
    python -m codemap <path> --prompt-file <file>  # Analyze a specific prompt file
    python -m codemap <path> --behavioral       # Behavioral analysis (call graph, state flow, dead code)
    python -m codemap <path> --runtime-analysis # Universal runtime analysis
"""

import argparse
import json
import os
import sys
from pathlib import Path

from codemap.extractors import get_extractor
from codemap.extractors.config_parser import parse_config
from codemap.core.graph_builder import GraphBuilder
from codemap.core.community import (
    detect_communities, find_surprising_links, find_god_nodes,
    find_paths, get_entity_context, _community_display_name,
)
from codemap.core.analyzers import LayerViolationAnalyzer, CircularDependencyAnalyzer
from codemap.core.cache import (
    get_changed_files, load_cache, save_cache, get_cached_graph, save_graph,
)
from codemap.exporters.json_exporter import export_json
from codemap.exporters.html_exporter import export_html
from codemap.exporters.mermaid_exporter import export_mermaid
from codemap.exporters.report_exporter import export_report
from codemap.core.utils import get_project_root, collect_files, should_ignore

# Instruction Pipeline (v3)
try:
    from codemap.instructions import InstructionGraphBuilder, PromptExtractor
    HAS_INSTRUCTION_PIPELINE = True
except ImportError:
    HAS_INSTRUCTION_PIPELINE = False

# Runtime Analyzers (v4)
try:
    from codemap.analyzers import (
        EntryDetector, ConfigScanner,
        TestCoverageScanner, ConventionDetector,
    )
    HAS_RUNTIME_ANALYZERS = True
except ImportError:
    HAS_RUNTIME_ANALYZERS = False


OUTPUT_DIR = ".codemap"

# File extensions that contain instruction/prompt content
PROMPT_EXTENSIONS = {
    ".dart", ".py", ".js", ".jsx", ".ts", ".tsx",
    ".md", ".txt", ".yaml", ".yml", ".json", ".prompt", ".instructions",
}


def detect_project_info(root: Path) -> dict:
    """Detect project metadata from config files.

    For monorepos, checks subdirectories (apps/*, packages/*) for config files
    if nothing is found at the root.
    """
    info = {
        "name": root.name,
        "language": "Unknown",
        "framework": "Unknown",
        "files_analyzed": 0,
    }

    # Check for pubspec.yaml (Flutter/Dart) — root first, then subdirectories
    pubspec = root / "pubspec.yaml"
    if not pubspec.exists():
        # Monorepo: check apps/* and packages/*
        for subdir in ["apps", "packages"]:
            search_dir = root / subdir
            if search_dir.exists():
                for child in search_dir.iterdir():
                    candidate = child / "pubspec.yaml"
                    if candidate.exists():
                        pubspec = candidate
                        break
            if pubspec.exists():
                break

    if pubspec.exists():
        config = parse_config(pubspec)
        if config:
            # For monorepos, prefer the root directory name over a sub-package name
            if pubspec.parent != root:
                info["name"] = root.name
            else:
                info["name"] = config.get("name", root.name)
            info["language"] = "Dart"
            info["framework"] = "Flutter" if config.get("flutter") else "Dart"
            info["type"] = config.get("type", "dart_package")

    # Check for package.json (Node.js)
    pkg_json = root / "package.json"
    if pkg_json.exists():
        config = parse_config(pkg_json)
        if config:
            info["name"] = config.get("name", root.name)
            info["language"] = "JavaScript/TypeScript"
            info["framework"] = "Node.js"
            info["type"] = config.get("type", "node_package")

    # Check for pyproject.toml (Python)
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        config = parse_config(pyproject)
        if config:
            info["name"] = config.get("name", root.name)
            info["language"] = "Python"
            info["framework"] = "Python"
            info["type"] = config.get("type", "python_package")

    # Check for Cargo.toml (Rust)
    cargo = root / "Cargo.toml"
    if cargo.exists():
        info["language"] = "Rust"
        info["framework"] = "Rust"
        info["type"] = "rust_package"

    # Check for go.mod (Go)
    gomod = root / "go.mod"
    if gomod.exists():
        info["language"] = "Go"
        info["framework"] = "Go"
        info["type"] = "go_module"

    return info


def collect_prompt_files(
    root: Path,
    scan_dirs: list = None,
    ignore_patterns: list = None,
) -> list:
    """Collect files that may contain instructions/prompts."""
    if ignore_patterns is None:
        ignore_patterns = []

    files = []
    search_dirs = [root] if not scan_dirs else [
        root / d for d in scan_dirs if (root / d).exists()
    ]

    for search_dir in search_dirs:
        for path in search_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in PROMPT_EXTENSIONS:
                continue
            if should_ignore(path, ignore_patterns, root):
                continue
            # Skip very small files (likely not instructions)
            try:
                if path.stat().st_size < 200:
                    continue
            except OSError:
                continue
            files.append(path)

    return sorted(files)


def run_instruction_analysis(
    target: str,
    scan_dirs: list = None,
    ignore_patterns: list = None,
    output_dir: str = OUTPUT_DIR,
    prompt_file: str = None,
) -> dict:
    """Run the instruction analysis pipeline."""
    if not HAS_INSTRUCTION_PIPELINE:
        print("❌ Instruction pipeline not available. Check installation.")
        print("   Required: no additional dependencies (uses built-in analysis)")
        return {}

    root = get_project_root(target)
    out = root / output_dir

    print(f"🔍 Codemap Instruction Analysis — Scanning {root}")

    builder = InstructionGraphBuilder()
    all_graphs = []

    if prompt_file:
        # Analyze a specific file
        fp = Path(prompt_file)
        if not fp.is_absolute():
            fp = root / fp
        if not fp.exists():
            print(f"❌ File not found: {fp}")
            return {}
        print(f"📄 Analyzing: {fp.name}")
        graph = builder.analyze_file(fp)
        if graph:
            all_graphs.append(graph)
    else:
        # Scan for prompt files
        files = collect_prompt_files(root, scan_dirs, ignore_patterns or [])
        print(f"📁 Found {len(files)} potential instruction files")

        for f in files:
            graph = builder.analyze_file(f)
            if graph and graph.redundancies:
                all_graphs.append(graph)
                print(f"  🔎 {f.name}: {len(graph.redundancies)} redundancies found")

    if not all_graphs:
        print("✅ No instruction redundancies detected")
        return {"instruction_analysis": {"files_analyzed": 0, "total_redundancies": 0}}

    # Build combined report
    total_redundancies = sum(len(g.redundancies) for g in all_graphs)
    total_chunks = sum(len(g.chunks) for g in all_graphs)
    total_clusters = sum(len(g.clusters) for g in all_graphs)

    print(f"\n📊 Instruction Analysis Summary:")
    print(f"   Files analyzed: {len(all_graphs)}")
    print(f"   Total chunks: {total_chunks}")
    print(f"   Total redundancies: {total_redundancies}")
    print(f"   Total clusters: {total_clusters}")

    # Save instruction analysis to separate JSON
    instruction_data = {
        "files": [g.to_dict() for g in all_graphs],
        "combined_summary": {
            "files_analyzed": len(all_graphs),
            "total_chunks": total_chunks,
            "total_redundancies": total_redundancies,
            "total_clusters": total_clusters,
            "critical_count": sum(
                1 for g in all_graphs
                for r in g.redundancies
                if r.severity == "critical"
            ),
            "high_count": sum(
                1 for g in all_graphs
                for r in g.redundancies
                if r.severity == "high"
            ),
        },
    }

    # Save outputs
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "instruction_analysis.json", "w") as f:
        json.dump(instruction_data, f, indent=2)

    # Append to report
    _append_instruction_report(instruction_data, out / "GRAPH_REPORT.md")

    print(f"\n✅ Instruction analysis saved to {out}/")
    print(f"   📄 instruction_analysis.json")
    print(f"   📊 GRAPH_REPORT.md (updated)")

    return instruction_data


def _append_instruction_report(data: dict, report_path: Path):
    """Append instruction analysis section to the main report."""
    summary = data.get("combined_summary", {})
    files = data.get("files", [])

    lines = [
        "",
        "---",
        "",
        "## Instruction Redundancy Analysis",
        "",
        "Automated detection of instruction redundancies, semantic duplicates, and scope conflicts in prompt files.",
        "",
        "### Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| **Files analyzed** | {summary.get('files_analyzed', 0)} |",
        f"| **Total chunks** | {summary.get('total_chunks', 0)} |",
        f"| **Total redundancies** | {summary.get('total_redundancies', 0)} |",
        f"| **Total clusters** | {summary.get('total_clusters', 0)} |",
        f"| **Critical issues** | {summary.get('critical_count', 0)} |",
        f"| **High severity** | {summary.get('high_count', 0)} |",
        "",
    ]

    # Per-file breakdown
    for file_data in files:
        fname = file_data.get("source_file", "unknown")
        fsummary = file_data.get("summary", {})
        redundancies = file_data.get("redundancies", [])
        clusters = file_data.get("clusters", [])

        if not redundancies:
            continue

        lines.extend([
            f"### {fname}",
            "",
            f"Chunks: {fsummary.get('total_chunks', 0)} | "
            f"Redundancies: {fsummary.get('total_redundancies', 0)} | "
            f"Redundancy rate: {fsummary.get('redundancy_rate', 0)}%",
            "",
        ])

        # Most duplicated topics
        most_duped = fsummary.get("most_duplicated_topics", [])
        if most_duped:
            lines.append("**Most duplicated topics:**")
            for item in most_duped:
                lines.append(f"- `{item['topic']}`: {item['chunk_count']} chunks")
            lines.append("")

        # Critical and high redundancies
        critical = [r for r in redundancies if r["severity"] in ("critical", "high")]
        if critical:
            lines.append("**Critical/High Redundancies:**")
            lines.append("")
            lines.append("| # | Type | Severity | Evidence | Recommendation |")
            lines.append("|---|------|----------|----------|----------------|")
            for i, r in enumerate(critical[:10], 1):
                lines.append(
                    f"| {i} | {r['type']} | {r['severity']} | "
                    f"{r['evidence'][:60]} | {r['recommendation'][:50]} |"
                )
            lines.append("")

        # Clusters
        if clusters:
            lines.append("**Redundancy Clusters:**")
            lines.append("")
            for c in clusters:
                lines.append(
                    f"- **{c['id']}** ({c['topic']}): "
                    f"{len(c['chunk_ids'])} chunks, severity: {c['severity']}"
                )
                lines.append(f"  - {c['recommendation']}")
            lines.append("")

    # Append to existing report
    existing = ""
    if report_path.exists():
        existing = report_path.read_text(encoding="utf-8", errors="replace")

    # Don't duplicate the section if it already exists
    if "Instruction Redundancy Analysis" in existing:
        # Replace existing section
        idx = existing.find("## Instruction Redundancy Analysis")
        if idx > 0:
            existing = existing[:idx]

    with open(report_path, "w") as f:
        f.write(existing)
        f.write("\n".join(lines))
        f.write(f"\n\n---\n*Generated by Codemap — Instruction Pipeline*\n")


def run_pipeline(
    target: str,
    scan_dirs: list = None,
    ignore_patterns: list = None,
    output_dir: str = OUTPUT_DIR,
    refresh: bool = False,
    ast_only: bool = False,
    filters: list = None,
) -> dict:
    """Run the full codemap pipeline."""
    root = get_project_root(target)
    out = root / output_dir
    cache_dir = out / "cache"

    print(f"🕸️  Codemap — Scanning {root}")

    # Check cache
    if not refresh:
        cached = get_cached_graph(out)
        if cached:
            print(f"📦 Cache found: {cached['metadata'].get('entity_count', 0)} entities")
            return cached

    # Collect files
    files = collect_files(root, scan_dirs, ignore_patterns or [])
    print(f"📁 Found {len(files)} source files")

    # Build graph
    builder = GraphBuilder()

    for f in files:
        try:
            extractor = get_extractor(str(f))
            result = extractor.extract(f, root)
            builder.add_result(result)
        except Exception as e:
            print(f"  ⚠️  Error extracting {f.name}: {e}")

    # Parse config files
    config_files = ["pubspec.yaml", "package.json", "pyproject.toml", "Cargo.toml"]
    for cf in config_files:
        p = root / cf
        if p.exists():
            config = parse_config(p)
            if config:
                from codemap.extractors.base import Entity
                builder.add_result(type('R', (), {
                    'entities': [Entity(
                        id=cf, type="config", name=config.get("name", cf),
                        file=cf, metadata=config,
                    )],
                    'relationships': [],
                    'imports': [],
                    'exports': [],
                })())

    # Detect communities
    G = builder.build_networkx()
    communities = detect_communities(G)

    # Find god nodes
    god_nodes = find_god_nodes(G, top_n=10)

    # Find surprising links
    surprising = find_surprising_links(G, builder.entities)

    # Build project info
    project_info = detect_project_info(root)
    project_info["files_analyzed"] = len(files)

    # Convert communities to clusters
    clusters = []
    for comm_id, members in communities.items():
        name = _community_display_name(comm_id, members, G)
        clusters.append({
            "id": comm_id,
            "name": name,
            "members": members,  # keep full list; cap display in report only
            "description": f"{len(members)} entities",
        })

    # If no communities detected, use builder's file-based clusters
    if not clusters:
        clusters = builder.get_clusters(G)

    # Serialize graph
    graph_data = builder.to_dict(project_info, clusters, god_nodes, surprising)

    # Save outputs
    print(f"📊 Entities: {graph_data['metadata']['entity_count']}, "
          f"Relationships: {graph_data['metadata']['relationship_count']}, "
          f"Clusters: {len(clusters)}")

    export_json(graph_data, out / "graph.json")
    export_report(graph_data, out / "GRAPH_REPORT.md")
    export_mermaid(graph_data, out / "graph.mermaid")
    export_html(graph_data, out / "graph.html")

    # Save cache
    _, new_hashes = get_changed_files(files, cache_dir, root)
    save_cache(cache_dir, new_hashes)

    print(f"✅ Outputs saved to {out}/")
    return graph_data


def query_entity(target: str, entity_name: str, output_dir: str = OUTPUT_DIR):
    """Query a specific entity from the graph."""
    root = get_project_root(target)
    out = root / output_dir
    cached = get_cached_graph(out)

    if not cached:
        print("❌ No cached graph found. Run codemap first.")
        return

    # Build a quick lookup
    entities = {e["id"]: e for e in cached.get("entities", [])}
    relationships = cached.get("relationships", [])

    # Search for entity
    matches = []
    for eid, ent in entities.items():
        if entity_name.lower() in eid.lower() or entity_name.lower() in ent.get("name", "").lower():
            matches.append((eid, ent))

    if not matches:
        print(f"❌ No entity matching '{entity_name}'")
        return

    for eid, ent in matches:
        print(f"\n🔍 {ent['name']} ({ent['type']})")
        print(f"   File: {ent['file']}")
        if ent.get('line'):
            print(f"   Line: {ent['line']}")

        # Find relationships
        incoming = [r for r in relationships if r["target"] == eid]
        outgoing = [r for r in relationships if r["source"] == eid]

        if incoming:
            print(f"   ← Incoming ({len(incoming)}):")
            for r in incoming[:10]:
                print(f"     {r['source']} --{r['type']}--> {eid}")

        if outgoing:
            print(f"   → Outgoing ({len(outgoing)}):")
            for r in outgoing[:10]:
                print(f"     {eid} --{r['type']}--> {r['target']}")


def find_path(target: str, source: str, dest: str, output_dir: str = OUTPUT_DIR):
    """Find path between two entities."""
    root = get_project_root(target)
    out = root / output_dir
    cached = get_cached_graph(out)

    if not cached:
        print("❌ No cached graph found. Run codemap first.")
        return

    import networkx as nx
    G = nx.DiGraph()
    for r in cached.get("relationships", []):
        G.add_edge(r["source"], r["target"], type=r["type"])

    # Find matching nodes
    source_nodes = [n for n in G.nodes() if source.lower() in n.lower()]
    dest_nodes = [n for n in G.nodes() if dest.lower() in n.lower()]

    if not source_nodes:
        print(f"❌ No entity matching '{source}'")
        return
    if not dest_nodes:
        print(f"❌ No entity matching '{dest}'")
        return

    for s in source_nodes[:3]:
        for d in dest_nodes[:3]:
            try:
                paths = list(nx.all_simple_paths(G, s, d, cutoff=8))
                if paths:
                    print(f"\n🛤️  Path: {s} → {d}")
                    for i, path in enumerate(paths[:3]):
                        print(f"  {' → '.join(path)}")
                else:
                    print(f"\n❌ No path found: {s} → {d}")
            except Exception:
                pass


def run_runtime_analysis(
    target: str,
    scan_dirs: list = None,
    ignore_patterns: list = None,
    output_dir: str = OUTPUT_DIR,
) -> dict:
    """Run universal runtime analysis."""
    if not HAS_RUNTIME_ANALYZERS:
        print("❌ Runtime analyzers not available.")
        return {}

    root = get_project_root(target)
    out = root / output_dir

    print(f"🔍 Codemap Runtime Analysis — Scanning {root}")

    # Collect files
    files = collect_files(root, scan_dirs, ignore_patterns or [])
    print(f"📁 Found {len(files)} source files")

    # Run all analyzers
    runtime_data = {}

    # 1. Entry Point Detection
    print("  🚪 Detecting entry points...")
    entry_detector = EntryDetector()
    entry_points = entry_detector.detect_all(root, files)
    runtime_data["entry_points"] = entry_detector.to_dict(entry_points)
    print(f"     Found {len(entry_points)} entry points")

    # 2. Config Surface Scanning
    print("  ⚙️  Scanning config surface...")
    config_scanner = ConfigScanner()
    config_report = config_scanner.scan_all(root, files)
    runtime_data["config_surface"] = config_report.to_dict()
    print(f"     Found {len(config_report.env_vars)} env vars, "
          f"{len(config_report.feature_flags)} feature flags, "
          f"{len(config_report.constants)} constants")

    # 3. Test Coverage Analysis
    print("  🧪 Analyzing test coverage...")
    test_scanner = TestCoverageScanner()
    test_report = test_scanner.scan_all(root, files)
    runtime_data["test_coverage"] = test_report.to_dict()
    print(f"     {len(test_report.test_files)} test files, "
          f"{len(test_report.untested_modules)} untested modules")

    # 4. Convention Detection
    print("  📏 Detecting conventions...")
    convention_detector = ConventionDetector()
    convention_report = convention_detector.detect_all(root, files)
    runtime_data["conventions"] = convention_report.to_dict()
    print(f"     Architecture: {convention_report.detected_architecture or 'unknown'}")
    print(f"     Frameworks: {', '.join(convention_report.detected_frameworks) or 'none detected'}")

    # Save outputs
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "runtime_analysis.json", "w") as f:
        json.dump(runtime_data, f, indent=2, default=str)

    # Append to report
    _append_runtime_report(runtime_data, out / "GRAPH_REPORT.md")

    print(f"\n✅ Runtime analysis saved to {out}/")
    print(f"   📄 runtime_analysis.json")
    print(f"   📊 GRAPH_REPORT.md (updated)")

    return runtime_data


def _append_runtime_report(data: dict, report_path: Path):
    """Append runtime analysis section to the main report."""
    lines = [
        "",
        "---",
        "",
        "## Runtime Comprehension",
        "",
        "Universal analysis of what the codebase does at runtime.",
        "",
    ]

    # Entry Points
    entry_data = data.get("entry_points", {})
    entry_points = entry_data.get("entry_points", [])
    if entry_points:
        lines.extend([
            "### Application Entry Points",
            "",
            "| File | Line | Type | Initializations |",
            "|------|------|------|-----------------|",
        ])
        for ep in entry_points[:10]:
            inits = ", ".join(i["name"] for i in ep.get("initializations", [])[:5])
            lines.append(
                f"| `{ep['file'].split('/')[-1]}` | {ep['line']} | "
                f"{ep['entry_type']} | {inits[:50]} |"
            )
        lines.append("")

    # Config Surface
    config_data = data.get("config_surface", {})
    summary = config_data.get("summary", {})
    if summary:
        lines.extend([
            "### Configuration Surface",
            "",
            "| Type | Count |",
            "|------|-------|",
            f"| Environment Variables | {summary.get('total_env_vars', 0)} |",
            f"| Config Files | {summary.get('total_config_files', 0)} |",
            f"| Feature Flags | {summary.get('total_feature_flags', 0)} |",
            f"| Constants | {summary.get('total_constants', 0)} |",
            f"| API URLs | {summary.get('total_api_urls', 0)} |",
            f"| Secrets | {summary.get('total_secrets', 0)} |",
            "",
        ])

        # List env vars if any
        env_vars = config_data.get("env_vars", [])
        if env_vars:
            lines.append("**Environment Variables:**")
            for ev in env_vars[:10]:
                secret_flag = " 🔒" if ev.get("is_secret") else ""
                lines.append(f"- `{ev['name']}` (in {ev['file'].split('/')[-1]}:{ev['line']}{secret_flag})")
            lines.append("")

    # Test Coverage
    test_data = data.get("test_coverage", {})
    test_summary = test_data.get("summary", {})
    if test_summary:
        lines.extend([
            "### Test Coverage",
            "",
            f"- **Test files**: {test_summary.get('total_test_files', 0)}",
            f"- **Test cases**: {test_summary.get('total_test_cases', 0)}",
            f"- **Source files**: {test_summary.get('total_source_files', 0)}",
            f"- **Coverage**: {test_summary.get('coverage_percentage', 0)}%",
            f"- **High-risk untested modules**: {test_summary.get('high_risk_modules', 0)}",
            "",
        ])

        # List untested modules
        untested = test_data.get("untested_modules", [])
        if untested:
            lines.append("**Untested Modules:**")
            for mod in untested[:10]:
                lines.append(f"- `{mod.split('/')[-1]}`")
            lines.append("")

    # Conventions
    conv_data = data.get("conventions", {})
    if conv_data:
        lines.extend([
            "### Codebase Conventions",
            "",
        ])

        file_naming = conv_data.get("file_naming", {})
        if file_naming:
            lines.append(f"- **File naming**: {file_naming.get('dominant', 'unknown')}")

        class_naming = conv_data.get("class_naming", {})
        if class_naming:
            lines.append(f"- **Class naming**: {class_naming.get('dominant', 'unknown')}")

        arch = conv_data.get("detected_architecture")
        if arch:
            lines.append(f"- **Architecture**: {arch}")

        frameworks = conv_data.get("detected_frameworks", [])
        if frameworks:
            lines.append(f"- **Frameworks**: {', '.join(frameworks)}")

        dir_struct = conv_data.get("directory_structure", {})
        if dir_struct:
            lines.append(f"- **Directory pattern**: {dir_struct.get('pattern', 'unknown')}")

        error_handling = conv_data.get("error_handling", {})
        if error_handling:
            patterns = ", ".join(error_handling.keys())
            lines.append(f"- **Error handling**: {patterns}")

        lines.append("")

    # Append to existing report
    existing = ""
    if report_path.exists():
        existing = report_path.read_text(encoding="utf-8", errors="replace")

    # Don't duplicate the section
    if "Runtime Comprehension" in existing:
        idx = existing.find("## Runtime Comprehension")
        if idx > 0:
            existing = existing[:idx]

    with open(report_path, "w") as f:
        f.write(existing)
        f.write("\n".join(lines))
        f.write(f"\n\n---\n*Generated by Codemap — Runtime Analyzers*\n")


def run_behavioral_analysis_pipeline(
    target: str,
    graph_data: dict,
    output_dir: str = OUTPUT_DIR,
) -> dict:
    """Run behavioral analysis: language-specific extraction + Python analysis."""
    from codemap.behavioral.extractors import detect_language, run_extractor

    root = get_project_root(target)
    out = root / output_dir

    print(f"🧠 Codemap Behavioral Analysis — Scanning {root}")

    # Step 1: Detect language and run appropriate extractor
    language = detect_language(root)
    if not language:
        print("  ⚠️  No behavioral extractor available for this project's language.")
        print("     Supported: Dart (add more via codemap/behavioral/extractors/)")
        return {}

    print(f"  📐 Running {language} behavioral extractor...")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        success = run_extractor(language, root, tmp_path)
        if not success:
            print(f"  ❌ {language} extractor failed")
            return {}
    except Exception as e:
        print(f"  ❌ Extractor error: {e}")
        return {}

    # Step 2: Run Python behavioral analyzers
    print("  🔬 Running behavioral analyzers...")
    try:
        from codemap.behavioral import run_behavioral_analysis
        results = run_behavioral_analysis(graph_data, tmp_path)
    except Exception as e:
        print(f"  ❌ Behavioral analysis failed: {e}")
        return {}
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Step 3: Save results
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "behavioral_analysis.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Step 4: Append to report
    _append_behavioral_report(results, out / "GRAPH_REPORT.md")

    summary = results.get('summary', {})
    print(f"\n✅ Behavioral analysis saved to {out}/")
    print(f"   📄 behavioral_analysis.json")
    print(f"   📊 GRAPH_REPORT.md (updated)")
    print(f"   Dead code: {summary.get('dead_functions', 0)} | "
          f"Hot paths: {summary.get('hot_paths', 0)} | "
          f"State mutations: {summary.get('total_state_mutations', 0)} | "
          f"Unpaired listeners: {summary.get('unpaired_listeners', 0)}")

    return results


def _append_behavioral_report(data: dict, report_path: Path):
    """Append behavioral analysis section to the main report."""
    summary = data.get('summary', {})
    lines = [
        "",
        "---",
        "",
        "## Behavioral Analysis",
        "",
        f"*{summary.get('files_analyzed', 0)} files analyzed via AST*",
        "",
    ]

    # ── Dead Code ──
    dead_code = data.get('dead_code', [])
    if dead_code:
        lines.extend([
            "### Dead Code (Unreachable from Entry Points)",
            "",
            f"*{len(dead_code)} functions detected*",
            "",
            "| Function | File | Calls Out | Called By |",
            "|----------|------|-----------|-----------|",
        ])
        for d in dead_code[:15]:
            lines.append(
                f"| `{d['function']}` | {d['file'][:40]} | "
                f"{d['calls_count']} | {d['called_by_count']} |"
            )
        lines.append("")

    # ── Hot Paths ──
    hot_paths = data.get('hot_paths', [])
    if hot_paths:
        lines.extend([
            "### Hot Paths (Most-Called Functions)",
            "",
            "| Function | File | Callers |",
            "|----------|------|---------|",
        ])
        for h in hot_paths[:10]:
            lines.append(
                f"| `{h['function']}` | {h['file'][:40]} | {h['callers']} |"
            )
        lines.append("")

    # ── Call Depth ──
    call_depth = data.get('call_depth', [])
    if call_depth:
        lines.extend([
            "### Deepest Call Chains",
            "",
            "| Function | File | Depth |",
            "|----------|------|-------|",
        ])
        for d in call_depth[:5]:
            lines.append(
                f"| `{d['function']}` | {d['file'][:40]} | {d['depth']} |"
            )
        lines.append("")

    # ── State Mutation Hotspots ──
    hotspots = data.get('mutation_hotspots', [])
    if hotspots:
        lines.extend([
            "### State Mutation Hotspots",
            "",
            "| Class | Mutations | Risk | Breakdown |",
            "|-------|-----------|------|-----------|",
        ])
        for h in hotspots[:10]:
            breakdown = ", ".join(f"{k}:{v}" for k, v in h['breakdown'].items())
            lines.append(
                f"| `{h['class']}` | {h['mutations']} | "
                f"{h['risk']} | {breakdown[:50]} |"
            )
        lines.append("")

    # ── Unpaired Listeners (Memory Leaks) ──
    unpaired = data.get('unpaired_listeners', [])
    if unpaired:
        problematic = [u for u in unpaired if u['unpaired'] > 0]
        lines.extend([
            "### Listener Health",
            "",
        ])
        if problematic:
            lines.extend([
                f"⚠️ **{len(problematic)} components with unpaired listeners** (potential memory leaks):",
                "",
                "| Component | Added | Removed | Unpaired |",
                "|-----------|-------|---------|----------|",
            ])
            for u in problematic:
                name = u.get('component', u.get('widget', ''))
                lines.append(
                    f"| `{name}` | {u['listeners_added']} | "
                    f"{u['listeners_removed']} | {u['unpaired']} |"
                )
            lines.append("")

        paired = [u for u in unpaired if u['unpaired'] == 0]
        if paired:
            lines.append(f"✅ {len(paired)} components with properly paired listeners.")
        lines.append("")

    # ── Lifecycle Summary ──
    lc = data.get('lifecycle_summary', {})
    if lc:
        lines.extend([
            "### Component Lifecycle Summary",
            "",
            f"- Total components: {lc.get('total_components', lc.get('total_widgets', 0))}",
            f"- Init hooks: {lc.get('with_init', lc.get('with_initState', 0))}",
            f"- Dispose hooks: {lc.get('with_dispose', 0)}",
            f"- Update hooks: {lc.get('with_update', lc.get('with_didChangeDependencies', 0))}",
            f"- Build/render hooks: {lc.get('with_build', 0)}",
            f"- State change hooks: {lc.get('with_state_change', 0)}",
            "",
        ])

    # Append to report
    existing = ""
    if report_path.exists():
        existing = report_path.read_text(encoding="utf-8", errors="replace")

    # Don't duplicate
    if "## Behavioral Analysis" in existing:
        idx = existing.find("## Behavioral Analysis")
        if idx > 0:
            existing = existing[:idx]

    with open(report_path, "w") as f:
        f.write(existing)
        f.write("\n".join(lines))
        f.write(f"\n\n---\n*Generated by Codemap — Behavioral Analysis*\n")


def main():
    parser = argparse.ArgumentParser(
        description="Codemap — Knowledge graph generator for codebases"
    )
    parser.add_argument("target", nargs="?", default=".",
                        help="Target directory to scan")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-scan (ignore cache)")
    parser.add_argument("--json", action="store_true",
                        help="Output only graph.json")
    parser.add_argument("--report", action="store_true",
                        help="Output only GRAPH_REPORT.md")
    parser.add_argument("--html", action="store_true",
                        help="Output only graph.html")
    parser.add_argument("--mermaid", action="store_true",
                        help="Output only Mermaid diagram")
    parser.add_argument("--ast-only", action="store_true",
                        help="AST-only extraction (no LLM)")
    parser.add_argument("--scan-dirs", nargs="*",
                        help="Directories to scan (default: all)")
    parser.add_argument("--ignore", nargs="*",
                        help="Additional patterns to ignore")
    parser.add_argument("--output", default=OUTPUT_DIR,
                        help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_argument("--query", metavar="ENTITY",
                        help="Query a specific entity")
    parser.add_argument("--path", nargs=2, metavar=("SOURCE", "DEST"),
                        help="Find path between two entities")
    parser.add_argument("--analyze-prompts", action="store_true",
                        help="Analyze instruction files for redundancies")
    parser.add_argument("--prompt-file", metavar="FILE",
                        help="Analyze a specific prompt/instruction file")
    parser.add_argument("--runtime-analysis", action="store_true",
                        help="Run universal runtime analysis")
    parser.add_argument("--behavioral", action="store_true",
                        help="Run behavioral analysis (call graph, state flow, dead code)")

    args = parser.parse_args()

    if args.query:
        query_entity(args.target, args.query, args.output)
        return

    if args.path:
        find_path(args.target, args.path[0], args.path[1], args.output)
        return

    if args.analyze_prompts or args.prompt_file:
        run_instruction_analysis(
            target=args.target,
            scan_dirs=args.scan_dirs,
            ignore_patterns=args.ignore,
            output_dir=args.output,
            prompt_file=args.prompt_file,
        )
        return

    if args.runtime_analysis:
        run_runtime_analysis(
            target=args.target,
            scan_dirs=args.scan_dirs,
            ignore_patterns=args.ignore,
            output_dir=args.output,
        )
        return

    graph_data = run_pipeline(
        target=args.target,
        scan_dirs=args.scan_dirs,
        ignore_patterns=args.ignore,
        output_dir=args.output,
        refresh=args.refresh,
        ast_only=args.ast_only,
    )

    # Run behavioral analysis if requested
    if args.behavioral:
        run_behavioral_analysis_pipeline(
            target=args.target,
            graph_data=graph_data,
            output_dir=args.output,
        )

    if args.json:
        print(json.dumps(graph_data, indent=2))
    elif args.report:
        from codemap.exporters.report_exporter import export_report
        out = get_project_root(args.target) / args.output
        export_report(graph_data, out / "GRAPH_REPORT.md")
        print(f"📄 Report: {out}/GRAPH_REPORT.md")
    elif args.html:
        from codemap.exporters.html_exporter import export_html
        out = get_project_root(args.target) / args.output
        export_html(graph_data, out / "graph.html")
        print(f"🌐 HTML: {out}/graph.html")
    elif args.mermaid:
        from codemap.exporters.mermaid_exporter import export_mermaid
        out = get_project_root(args.target) / args.output
        export_mermaid(graph_data, out / "graph.mermaid")
        print(f"📐 Mermaid: {out}/graph.mermaid")


if __name__ == "__main__":
    main()
