"""Python extractor — regex-based AST parsing."""

import re
from pathlib import Path

from codemap.extractors.base import BaseExtractor, Entity, ExtractionResult, Relationship


class PythonExtractor(BaseExtractor):
    """Extract entities and relationships from Python files."""

    RE_IMPORT = re.compile(r"""(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))""")
    RE_CLASS = re.compile(
        r"""class\s+(\w+)(?:\s*\(([^)]*)\))?\s*:"""
    )
    RE_FUNCTION = re.compile(
        r"""(?:def|async\s+def)\s+(\w+)\s*\("""
    )
    RE_DECORATOR = re.compile(r"""@(\w+)""")
    RE_ROUTE = re.compile(
        r"""@(?:app|router)\.(?:get|post|put|delete|patch|route)\s*\(['"]([^'"]+)['"]"""
    )
    RE_MODEL = re.compile(
        r"""class\s+(\w+).*?(?:BaseModel|Schema|Document)"""
    )

    def extract(self, file_path: Path, root: Path) -> ExtractionResult:
        content = self._read_file(file_path)
        if not content:
            return ExtractionResult()

        result = ExtractionResult()
        file_id = self._file_id(file_path, root)

        result.entities.append(Entity(
            id=file_id, type="module", name=file_path.name, file=file_id,
            metadata={"lines": len(content.split("\n"))},
        ))

        # Imports
        for m in self.RE_IMPORT.finditer(content):
            mod = m.group(1) or m.group(2)
            if mod:
                result.imports.append(mod)
                parts = mod.split(".")
                # Try to resolve to a file
                for i in range(len(parts), 0, -1):
                    candidate = (root / "/".join(parts[:i])).with_suffix(".py")
                    if candidate.exists():
                        target = str(candidate.relative_to(root))
                        result.relationships.append(Relationship(
                            source=file_id, target=target, type="imports",
                            confidence="EXTRACTED",
                            evidence=f"import {mod}",
                        ))
                        break

        # Classes
        for m in self.RE_CLASS.finditer(content):
            name = m.group(1)
            bases = self._parse_bases(m.group(2))
            result.entities.append(Entity(
                id=name, type="class", name=name, file=file_id,
                line=self._line_of(content, m.start()),
            ))
            for b in bases:
                if b and b not in ("object", "ABC", "Enum"):
                    result.relationships.append(Relationship(
                        source=name, target=b, type="extends",
                        confidence="EXTRACTED",
                        evidence=f"class {name} extends {b}",
                    ))

        # Functions
        for m in self.RE_FUNCTION.finditer(content):
            name = m.group(1)
            if name.startswith("_") and name != "__init__":
                continue
            result.entities.append(Entity(
                id=name, type="function", name=name, file=file_id,
                line=self._line_of(content, m.start()),
            ))

        # Routes (FastAPI/Flask)
        for m in self.RE_ROUTE.finditer(content):
            path = m.group(1)
            result.entities.append(Entity(
                id=f"route:{path}", type="route", name=path, file=file_id,
                line=self._line_of(content, m.start()),
            ))

        # Pydantic/Django models
        for m in self.RE_MODEL.finditer(content):
            name = m.group(1)
            for ent in result.entities:
                if ent.id == name:
                    ent.type = "schema"
                    break

        return result

    def _parse_bases(self, bases_str: str) -> list:
        if not bases_str:
            return []
        return [b.strip().split(",")[0].strip() for b in bases_str.split(",") if b.strip()]

    def _line_of(self, content: str, pos: int) -> int:
        return content[:pos].count("\n") + 1
