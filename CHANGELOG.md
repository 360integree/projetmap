# Changelog

All notable changes to Projetmap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-04

### Added

- **Core Features**
  - Structural analysis: Extract classes, functions, imports, and relationships
  - Community detection using Leiden modularity with greedy fallback
  - God node detection for identifying architectural bottlenecks
  - Incremental scanning with SHA256-based caching

- **Behavioral Analysis**
  - Dead code detection via BFS reachability from entry points
  - State mutation hotspot identification
  - Listener health analysis (unpaired add/remove detection)
  - Hot path analysis via call graph in-degree
  - Pluggable language-specific extractors (Dart, Python, JS/TS)

- **Export Formats**
  - JSON output for programmatic access
  - Markdown reports for human readability
  - Interactive HTML visualization with vis.js
  - Mermaid diagrams for documentation

- **Runtime Comprehension**
  - Entry point detection
  - Configuration surface scanning
  - Test coverage analysis
  - Convention detection

- **Instruction Analysis**
  - Prompt/instruction file chunking and classification
  - Redundancy detection
  - Scope conflict identification

- **CLI Interface**
  - Comprehensive command-line options
  - Entity querying and path finding
  - Directory and pattern filtering

- **MCP Server**
  - 8 tools for IDE integration
  - stdio transport for AI agent compatibility
  - Works with Cursor, Claude Desktop, ZCode, and Windsurf

- **Project Infrastructure**
  - PyPI package with `pip install projetmap`
  - GitHub Actions CI/CD
  - Comprehensive documentation
  - Contributing guidelines
  - Issue and PR templates

### Supported Languages

- Dart/Flutter (full behavioral analysis)
- Python (structural + behavioral)
- JavaScript/TypeScript (structural + behavioral)
- Any language (regex-based fallback)

## [Unreleased]

### Planned

- Python AST-based behavioral extractor
- JavaScript/TypeScript AST-based behavioral extractor
- VS Code extension
- Web-based visualization dashboard
- Batch analysis mode
- Custom rule definitions
