"""Tests for structural extractors."""

import pytest


def test_import_extractors():
    """Test that extractors can be imported."""
    from projetmap.extractors import EXTRACTORS, get_extractor

    assert EXTRACTORS is not None
    assert callable(get_extractor)


def test_extractors_dict_has_languages():
    """Test that EXTRACTORS dict has expected language extensions."""
    from projetmap.extractors import EXTRACTORS

    assert ".py" in EXTRACTORS
    assert ".dart" in EXTRACTORS
    assert ".js" in EXTRACTORS
    assert ".ts" in EXTRACTORS


def test_get_extractor_python():
    """Test get_extractor returns Python extractor for .py files."""
    from projetmap.extractors import get_extractor
    from projetmap.extractors.python import PythonExtractor

    extractor = get_extractor("test.py")
    assert isinstance(extractor, PythonExtractor)


def test_get_extractor_dart():
    """Test get_extractor returns Dart extractor for .dart files."""
    from projetmap.extractors import get_extractor
    from projetmap.extractors.dart import DartExtractor

    extractor = get_extractor("test.dart")
    assert isinstance(extractor, DartExtractor)


def test_get_extractor_unknown_falls_back():
    """Test get_extractor falls back to generic for unknown extensions."""
    from projetmap.extractors import get_extractor
    from projetmap.extractors.generic import GenericExtractor

    extractor = get_extractor("test.unknown")
    assert isinstance(extractor, GenericExtractor)
