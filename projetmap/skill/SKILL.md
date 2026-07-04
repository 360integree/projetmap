---
name: projetmap
description: Knowledge graph generator for codebases — wrapper for Projetmap (github.com/360integree/projetmap). Use whenever the user types /projetmap, asks about codebase structure, wants to visualize dependencies, map modules, understand architecture, or generate a knowledge graph of their project.
---

# 🗺️ Projetmap

This skill provides a **knowledge graph generator** for codebases. Use `/projetmap` or ask about codebase structure, and this skill will invoke Projetmap for you.

## Tool Location

Projetmap lives at:
```
/Users/akinseye/.agents/skills/projetmap/
```

CLI entry point:
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py <path>
```

## Installation

### Option 1: Git Clone (Recommended)
```bash
git clone https://github.com/360integree/projetmap.git ~/.agents/skills/projetmap
chmod +x ~/.agents/skills/projetmap/bin/projetmap
```

### Option 2: Install Script
```bash
git clone https://github.com/360integree/projetmap.git /tmp/projetmap
bash /tmp/projetmap/install.sh
```

### Option 3: pip
```bash
pip install git+https://github.com/360integree/projetmap.git
```

## Cache-First Protocol ⚡

**ALWAYS follow this order when invoked:**

1. **CHECK CACHE** — Look for `.projetmap/graph.json` and `.projetmap/GRAPH_REPORT.md` in the project root. If they exist, load them immediately.

2. **LOAD FROM CACHE** — Read `.projetmap/graph.json` for entities/relationships, `.projetmap/GRAPH_REPORT.md` for architecture. Do NOT re-scan unless asked.

3. **ANSWER FROM CACHE** — Answer using cached graph data. You have full knowledge of modules, classes, services, relationships, god nodes, and clusters.

4. **RE-SCAN ONLY ON DEMAND** — Only scan when:
   - User passes `--refresh` or says "update the graph"
   - `.projetmap/` doesn't exist
   - User explicitly asks for a fresh scan

## CLI Usage

### Full Pipeline
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py .
```

### With User Journeys
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --journeys
```

### With Behavioral Analysis
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --behavioral
```

### Scoped Scan
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --scan-dirs lib apps
```

### Specific Output
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --report
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --json
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --html
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --mermaid
```

### Force Refresh
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --refresh
```

### Query Entity
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --query AuthService
```

### Find Path
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/projetmap.py . --path CopilotOrchestrator DeepSeekClient
```

## MCP Server (IDE Integration)

Start the MCP server for agent tool access:
```bash
python3 /Users/akinseye/.agents/skills/projetmap/scripts/server.py
```

This can be configured in opencode.json under `mcp.servers.projetmap`.

## Pipeline

| Phase | What It Does | Output |
|-------|-------------|--------|
| **1. Detect** | Walk directory, respect `.gitignore`, collect source files | File list |
| **2. Extract** | Parse ASTs via regex patterns, extract entities + relationships | Raw nodes/edges |
| **3. Build** | Construct NetworkX graph, merge duplicates, tag confidence | In-memory graph |
| **4. Cluster** | Leiden community detection, god nodes, surprising links | Clusters + metadata |
| **5. Export** | Generate 4 output files | `.projetmap/` |

## Output Files

- `.projetmap/graph.json` — Machine-readable knowledge graph
- `.projetmap/GRAPH_REPORT.md` — Human-readable architectural report
- `.projetmap/graph.html` — Interactive vis.js visualization
- `.projetmap/graph.mermaid` — Mermaid flowchart
- `.projetmap/behavioral_analysis.json` — Dead code, state mutations, listeners
- `.projetmap/runtime_analysis.json` — Entry points, config, test coverage
- `.projetmap/user_journeys.json` — User journey data
- `.projetmap/user_journeys.html` — Interactive journey visualization
- `.projetmap/USER_JOURNEYS.md` — User journey report

## Supported Languages

| Language | What It Captures |
|----------|------------------|
| Dart/Flutter | Classes, mixins, enums, GoRouter routes, Riverpod providers, Drift tables, imports |
| Python | Classes, functions, FastAPI/Flask routes, Pydantic models, imports |
| JavaScript/TypeScript | Classes, interfaces, types, React components, Express routes, imports |
| Any other | Classes, functions, imports (regex fallback) |

## Mindset

- Prefer EXTRACTED relationships — only use INFERRED when there's clear signal
- God nodes reveal architects, bottlenecks, and refactoring targets
- Surprising cross-module links are refactoring signals
- The graph is a living artifact — commit `.projetmap/` to the repo

---

*Powered by Projetmap — Knowledge graph generator for codebases.*
