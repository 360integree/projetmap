# 🗺️ Projetmap

**Knowledge graph generator for codebases.**

[![PyPI version](https://badge.fury.io/py/projetmap.svg)](https://pypi.org/project/projetmap/)
[![Tests](https://github.com/360integree/codemap/actions/workflows/tests.yml/badge.svg)](https://github.com/360integree/codemap/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Turns any folder of code, docs, and configs into a queryable knowledge graph. Understand your codebase structure, dependencies, dead code, state mutations, and architectural patterns — all from a single CLI command.

## Quick Start

### Install from PyPI

```bash
pip install projetmap
```

### Or install from source

```bash
git clone https://github.com/360integree/codemap.git
cd codemap
pip install -e ".[full]"
```

### Scan a project

```bash
# Basic structural analysis
projetmap /path/to/your/project

# Or with Python module syntax
python -m projetmap /path/to/your/project

# With behavioral analysis (dead code, state flow, call graphs)
projetmap /path/to/your/project --behavioral
```

## What It Does

| Capability | Description |
|-----------|-------------|
| **Structural Analysis** | Extracts classes, functions, imports, and relationships from source code |
| **Community Detection** | Identifies logical clusters using Leiden modularity + path-based fallback |
| **Dead Code Detection** | BFS reachability from entry points — finds unreachable functions |
| **State Mutation Hotspots** | Classes with the most state changes (risk assessment) |
| **Listener Health** | Detects unpaired add/remove listeners (memory leak signals) |
| **Hot Path Analysis** | Most-called functions via call graph in-degree |
| **Instruction Analysis** | Detects redundancies, scope conflicts, and semantic duplicates in prompt files |
| **Runtime Comprehension** | Entry points, config surface, test coverage, convention detection |
| **God Node Detection** | Identifies overly-connected modules (architectural bottlenecks) |
| **Interactive HTML** | vis.js graph with clusters, search, drill-down, and dark theme |

## Supported Languages

- **Dart/Flutter** — Full behavioral analysis (AST-based)
- **Python** — Structural extraction + behavioral (extensible)
- **JavaScript/TypeScript** — Structural extraction + behavioral (extensible)
- **Any language** — Generic regex-based extraction as fallback

## CLI Reference

```bash
projetmap <path>                    # Full pipeline
projetmap <path> --refresh          # Force re-scan (ignore cache)
projetmap <path> --behavioral       # Include behavioral analysis
projetmap <path> --report           # Output only the Markdown report
projetmap <path> --json             # Output only graph.json
projetmap <path> --html             # Output only interactive HTML
projetmap <path> --mermaid          # Output only Mermaid diagram
projetmap <path> --query <entity>   # Query a specific entity
projetmap <path> --path A B         # Find path between entities
projetmap <path> --analyze-prompts  # Analyze instruction files
projetmap <path> --runtime-analysis # Runtime comprehension
projetmap <path> --scan-dirs lib    # Scan specific directories
projetmap <path> --ignore dist build  # Ignore patterns
```

## Output

Results are saved to `.projetmap/` in the target directory:

```
.projetmap/
├── graph.json                  # Full knowledge graph
├── GRAPH_REPORT.md             # Human-readable report
├── graph.html                  # Interactive vis.js visualization
├── graph.mermaid               # Mermaid diagram
├── behavioral_analysis.json    # Dead code, state mutations, listeners
├── runtime_analysis.json       # Entry points, config, tests, conventions
├── instruction_analysis.json   # Prompt/instruction redundancies
└── cache/
    └── file_hashes.json        # SHA256 hashes for incremental updates
```

## Architecture

```
projetmap/
├── core/               # Graph building, community detection, caching
├── extractors/         # Structural extractors (per-language, regex-based)
├── behavioral/         # Behavioral analysis layer
│   ├── extractors/     # Pluggable per-language AST extractors
│   │   ├── dart/       # Dart AST extractor (uses analyzer package)
│   │   └── (future: python/, js/)
│   ├── call_graph.py   # Dead code, hot paths (language-agnostic)
│   └── state_flow.py   # Mutation hotspots, listener health
├── exporters/          # JSON, Markdown, HTML, Mermaid output
├── analyzers/          # Runtime analysis (entry points, config, tests, conventions)
└── instructions/       # Instruction/prompt redundancy analysis
```

## Adding a Language Extractor

See `projetmap/behavioral/SCHEMA.md` for the full contract.

1. Create `projetmap/behavioral/extractors/<language>/`
2. Write an extractor that outputs `behavioral_data.json` matching the schema
3. Register it in `projetmap/behavioral/extractors/__init__.py`:
   ```python
   DETECTORS["python"] = (_detect_python, _run_python_extractor)
   ```

The Python analyzers (`call_graph.py`, `state_flow.py`) work automatically with any language's output.

## MCP Server (IDE Integration)

Projetmap includes an MCP server that AI agents in IDEs can call natively.

```bash
# Start the MCP server
projetmap mcp
```

### IDE Configuration

**Cursor** — add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "projetmap": {
      "command": "projetmap",
      "args": ["mcp"]
    }
  }
}
```

**Claude Desktop** — add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "projetmap": {
      "command": "projetmap",
      "args": ["mcp"]
    }
  }
}
```

**Windsurf** — add to your MCP configuration:
```json
{
  "mcpServers": {
    "projetmap": {
      "command": "projetmap",
      "args": ["mcp"]
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `projetmap_scan` | Scan a project and build the knowledge graph |
| `projetmap_report` | Get the full Markdown report |
| `projetmap_query` | Query an entity by name (details + relationships) |
| `projetmap_path` | Find dependency path between two entities |
| `projetmap_dead_code` | List dead code (unreachable functions) |
| `projetmap_hotspots` | State mutation hotspots (risk assessment) |
| `projetmap_listeners` | Unpaired listener warnings (memory leaks) |
| `projetmap_god_nodes` | Most-connected modules (architectural bottlenecks) |

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

### Quick Start (Development)

```bash
git clone https://github.com/360integree/codemap.git
cd codemap
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,full]"
pytest
```

## Dependencies

- Python 3.10+
- networkx ≥ 3.0
- pyyaml ≥ 6.0
- leidenalg ≥ 0.10.0 (optional, falls back to greedy modularity)
- mcp ≥ 1.0.0 (for MCP server / IDE integration)
- Dart SDK (only for Dart behavioral analysis)

## License

MIT — see [LICENSE](LICENSE) for details.
