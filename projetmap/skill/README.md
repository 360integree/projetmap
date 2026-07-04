# 🗺️ Projetmap

Knowledge graph generator for codebases. Scan, analyze, and visualize code structure.

## Features

- **Code Structure Graph** — Extract entities (classes, functions, modules) and relationships (imports, calls, extends)
- **User Journey Detection** — Trace user flows through screens, handlers, services, and data operations
- **Behavioral Analysis** — Dead code detection, state mutation hotspots, call depth analysis
- **Runtime Analysis** — Entry points, config surface, test coverage, convention detection
- **Instruction Analysis** — Find redundancies in prompts and documentation
- **Multiple Outputs** — JSON, Markdown report, interactive HTML visualization, Mermaid diagrams
- **MCP Server** — Expose tools to AI agents via Model Context Protocol

## Quick Start

### Install

```bash
git clone https://github.com/360integree/projetmap.git ~/.agents/skills/projetmap
chmod +x ~/.agents/skills/projetmap/bin/projetmap
```

### Usage

```bash
# Full scan
python3 ~/.agents/skills/projetmap/scripts/projetmap.py /path/to/project

# With user journeys
python3 ~/.agents/skills/projetmap/scripts/projetmap.py /path/to/project --journeys

# Just the report
python3 ~/.agents/skills/projetmap/scripts/projetmap.py /path/to/project --report
```

## Output Files

| File | Description |
|------|-------------|
| `.projetmap/graph.json` | Machine-readable knowledge graph |
| `.projetmap/GRAPH_REPORT.md` | Human-readable architectural report |
| `.projetmap/graph.html` | Interactive vis.js visualization |
| `.projetmap/user_journeys.json` | User journey data |
| `.projetmap/user_journeys.html` | Interactive journey visualization |
| `.projetmap/USER_JOURNEYS.md` | User journey report |

## MCP Server

Start the MCP server for agent tool access:

```bash
python3 ~/.agents/skills/projetmap/scripts/server.py
```

### Tools

| Tool | Description |
|------|-------------|
| `projetmap_scan` | Scan project and generate knowledge graph |
| `projetmap_journeys` | Get user journeys with optional feature filter |
| `projetmap_query` | Query a specific entity in the graph |
| `projetmap_report` | Get full GRAPH_REPORT.md |
| `projetmap_journeys_report` | Get full USER_JOURNEYS.md |

## Supported Languages

| Language | What It Captures |
|----------|------------------|
| Dart/Flutter | Classes, mixins, enums, GoRouter routes, Riverpod providers, Drift tables |
| Python | Classes, functions, FastAPI/Flask routes, Pydantic models |
| JavaScript/TypeScript | Classes, interfaces, types, React components, Express routes |
| Any other | Classes, functions, imports (regex fallback) |

## License

MIT
