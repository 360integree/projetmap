"""Tests for CLI entry point."""

import subprocess
import sys
from pathlib import Path

import pytest


def test_cli_help():
    """Test that CLI shows help."""
    result = subprocess.run(
        [sys.executable, "-m", "projetmap", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout or "usage:" in result.stdout.lower()


def test_cli_version():
    """Test that CLI shows version in package metadata."""
    import importlib.metadata

    version = importlib.metadata.version("projetmap")
    assert version == "1.0.1"


def test_cli_scan_project(sample_project):
    """Test scanning a sample project."""
    result = subprocess.run(
        [sys.executable, "-m", "projetmap", str(sample_project)],
        capture_output=True,
        text=True,
        cwd=str(sample_project.parent),
    )
    # Should complete without error
    assert result.returncode == 0


def test_cli_output_dir_created(sample_project):
    """Test that .projetmap directory is created after scan."""
    subprocess.run(
        [sys.executable, "-m", "projetmap", str(sample_project)],
        capture_output=True,
        text=True,
    )

    projetmap_dir = sample_project / ".projetmap"
    assert projetmap_dir.exists()


def test_cli_json_output(sample_project):
    """Test JSON output format."""
    subprocess.run(
        [sys.executable, "-m", "projetmap", str(sample_project), "--json"],
        capture_output=True,
        text=True,
    )

    json_file = sample_project / ".projetmap" / "graph.json"
    assert json_file.exists()


def test_cli_report_output(sample_project):
    """Test Markdown report output."""
    subprocess.run(
        [sys.executable, "-m", "projetmap", str(sample_project), "--report"],
        capture_output=True,
        text=True,
    )

    report_file = sample_project / ".projetmap" / "GRAPH_REPORT.md"
    assert report_file.exists()
