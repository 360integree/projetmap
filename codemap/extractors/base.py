"""Abstract base extractor for all language extractors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Entity:
    id: str
    type: str  # module, class, function, route, schema, config, enum, mixin
    name: str
    file: str
    line: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class Relationship:
    source: str
    target: str
    type: str  # imports, calls, extends, implements, composes, routes_to, configures, uses
    confidence: str = "EXTRACTED"  # EXTRACTED, INFERRED, AMBIGUOUS
    evidence: str = ""
    line: int = 0


@dataclass
class ExtractionResult:
    entities: List[Entity] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)


class BaseExtractor(ABC):
    """Abstract base for language-specific extractors."""

    @abstractmethod
    def extract(self, file_path: Path, root: Path) -> ExtractionResult:
        """Extract entities and relationships from a file."""
        pass

    def _file_id(self, file_path: Path, root: Path) -> str:
        """Generate file-level entity ID."""
        try:
            return str(file_path.relative_to(root))
        except ValueError:
            return str(file_path)

    def _class_id(self, name: str) -> str:
        return name

    def _function_id(self, name: str) -> str:
        return name

    def _read_file(self, file_path: Path) -> str:
        """Read file contents safely."""
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
