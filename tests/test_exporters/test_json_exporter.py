"""Tests for JSON exporter."""

import json
from pathlib import Path

import pytest


def test_import_json_exporter():
    """Test that JSON exporter can be imported."""
    from projetmap.exporters.json_exporter import export_json

    assert callable(export_json)


def test_json_exporter_exports_file(tmp_path):
    """Test that export_json creates a JSON file."""
    from projetmap.exporters.json_exporter import export_json

    output_file = tmp_path / "graph.json"

    # Create minimal graph data
    graph_data = {
        "nodes": [{"id": "test", "label": "Test"}],
        "edges": [],
    }

    # Export
    result = export_json(graph_data, output_file)

    assert output_file.exists()
    assert result == output_file

    # Verify content
    with open(output_file) as f:
        loaded = json.load(f)
    assert loaded == graph_data


def test_json_exporter_creates_directory(tmp_path):
    """Test that export_json creates parent directories."""
    from projetmap.exporters.json_exporter import export_json

    output_file = tmp_path / "subdir" / "graph.json"

    graph_data = {"nodes": [], "edges": []}
    export_json(graph_data, output_file)

    assert output_file.exists()
