# 🗺️ Codemap

**Knowledge graph generator for codebases.**

Turns any folder of code, docs, and configs into a queryable knowledge graph. Understand your codebase structure, dependencies, dead code, state mutations, and architectural patterns — all from a single CLI command.

## Quick Start

```bash
git clone https://github.com/user/codemap.git
cd codemap
pip install -r requirements.txt

# Scan a project
python -m codemap /path/to/your/project

# With behavioral analysis (dead code, state flow, call graphs)
python -m codemap /path/to/your/project --behavioral
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
python -m codemap <path>                    # Full pipeline
python -m codemap <path> --refresh          # Force re-scan (ignore cache)
python -m codemap <path> --behavioral       # Include behavioral analysis
python -m codemap <path> --report           # Output only the Markdown report
python -m codemap <path> --json             # Output only graph.json
python -m codemap <path> --html             # Output only interactive HTML
python -m codemap <path> --mermaid          # Output only Mermaid diagram
python -m codemap <path> --query <entity>   # Query a specific entity
python -m codemap <path> --path A B         # Find path between entities
python -m codemap <path> --analyze-prompts  # Analyze instruction files
python -m codemap <path> --runtime-analysis # Runtime comprehension
python -m codemap <path> --scan-dirs lib    # Scan specific directories
python -m codemap <path> --ignore dist build  # Ignore patterns
```

## Output

Results are saved to `.codemap/` in the target directory:

```
.codemap/
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
codemap/
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

See `codemap/behavioral/SCHEMA.md` for the full contract.

1. Create `codemap/behavioral/extractors/<language>/`
2. Write an extractor that outputs `behavioral_data.json` matching the schema
3. Register it in `codemap/behavioral/extractors/__init__.py`:
   ```python
   DETECTORS["python"] = (_detect_python, _run_python_extractor)
   ```

The Python analyzers (`call_graph.py`, `state_flow.py`) work automatically with any language's output.

## MCP Server (IDE Integration)

Codemap includes an MCP server that AI agents in IDEs can call natively.

```bash
# Start the MCP server
python -m codemap mcp
```

### IDE Configuration

**Cursor** — add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "codemap": {
      "command": "python3",
      "args": ["-m", "codemap", "mcp"],
      "cwd": "/path/to/codemap"
    }
  }
}
```

**Claude Desktop** — add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "codemap": {
      "command": "python3",
      "args": ["-m", "codemap", "mcp"],
      "cwd": "/path/to/codemap"
    }
  }
}
```

**ZCode** — add to `~/.zcode/cli/config.json` under `mcp.servers`:
```json
{
  "mcp": {
    "servers": {
      "codemap": {
        "type": "stdio",
        "command": "/path/to/codemap/.venv/bin/python3",
        "args": ["-m", "codemap", "mcp"],
        "env": {
          "PYTHONPATH": "/path/to/codemap"
        }
      }
    }
  }
}
```

**Windsurf** — add to your MCP configuration:
```json
{
  "mcpServers": {
    "codemap": {
      "command": "python3",
      "args": ["-m", "codemap", "mcp"],
      "cwd": "/path/to/codemap"
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `codemap_scan` | Scan a project and build the knowledge graph |
| `codemap_report` | Get the full Markdown report |
| `codemap_query` | Query an entity by name (details + relationships) |
| `codemap_path` | Find dependency path between two entities |
| `codemap_dead_code` | List dead code (unreachable functions) |
| `codemap_hotspots` | State mutation hotspots (risk assessment) |
| `codemap_listeners` | Unpaired listener warnings (memory leaks) |
| `codemap_god_nodes` | Most-connected modules (architectural bottlenecks) |

## Dependencies

- Python 3.10+
- networkx ≥ 3.0
- leidenalg ≥ 0.10.0 (optional, falls back to greedy modularity)
- pyyaml ≥ 6.0 (optional, for config parsing)
- mcp ≥ 1.0.0 (for MCP server / IDE integration)
- Dart SDK (only for Dart behavioral analysis)

## License

MIT
