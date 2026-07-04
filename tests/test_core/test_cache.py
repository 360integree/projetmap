"""Tests for cache module."""

import tempfile
from pathlib import Path

import pytest


def test_import_cache_functions():
    """Test that cache functions can be imported."""
    from projetmap.core.cache import file_hash, load_cache, save_cache

    assert callable(file_hash)
    assert callable(load_cache)
    assert callable(save_cache)


def test_file_hash():
    """Test file hash computation."""
    from projetmap.core.cache import file_hash

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content")
        f.flush()
        hash1 = file_hash(Path(f.name))
        hash2 = file_hash(Path(f.name))

    # Same file should produce same hash
    assert hash1 == hash2
    # Hash should be a hex string
    assert len(hash1) == 64  # SHA256 hex length


def test_load_cache_empty():
    """Test loading cache from empty directory."""
    from projetmap.core.cache import load_cache

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = load_cache(Path(tmpdir))
        assert cache == {}


def test_save_and_load_cache():
    """Test saving and loading cache."""
    from projetmap.core.cache import load_cache, save_cache

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        hashes = {"file1.py": "abc123", "file2.py": "def456"}
        save_cache(cache_dir, hashes)

        loaded = load_cache(cache_dir)
        assert loaded == hashes
