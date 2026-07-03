"""Structural extractors for different programming languages."""
from pathlib import Path

from codemap.extractors.base import BaseExtractor
from codemap.extractors.dart import DartExtractor
from codemap.extractors.python import PythonExtractor
from codemap.extractors.js_ts import JsTsExtractor
from codemap.extractors.generic import GenericExtractor

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
