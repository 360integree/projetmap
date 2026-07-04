"""Structural extractors for different programming languages."""
from pathlib import Path

from projetmap.extractors.base import BaseExtractor
from projetmap.extractors.dart import DartExtractor
from projetmap.extractors.generic import GenericExtractor
from projetmap.extractors.js_ts import JsTsExtractor
from projetmap.extractors.python import PythonExtractor

EXTRACTORS = {
    ".dart": DartExtractor,
    ".py": PythonExtractor,
    ".js": JsTsExtractor,
    ".jsx": JsTsExtractor,
    ".ts": JsTsExtractor,
    ".tsx": JsTsExtractor,
}


def get_extractor(filepath: str) -> BaseExtractor:
    """Get the appropriate extractor for a file."""
    ext = Path(filepath).suffix.lower()
    cls = EXTRACTORS.get(ext, GenericExtractor)
    return cls()
