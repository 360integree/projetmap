"""JavaScript/TypeScript extractor — regex-based AST parsing."""

import re
from pathlib import Path

from projetmap.extractors.base import BaseExtractor, Entity, ExtractionResult, Relationship


class JsTsExtractor(BaseExtractor):
    """Extract entities and relationships from JS/TS/JSX/TSX files."""

    RE_IMPORT = re.compile(
        r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|"""
        r"""require\s*\(\s*['"]([^'"]+)['"]\s*\))"""
    )
    RE_EXPORT = re.compile(
        r"""export\s+(?:default\s+)?(?:class|function|const|let|var|interface|type|enum)\s+(\w+)"""
    )
    RE_CLASS = re.compile(
        r"""(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?"""
        r"""(?:\s+implements\s+([\w\s,]+?))?\s*\{"""
    )
    RE_INTERFACE = re.compile(
        r"""(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([\w\s,]+?))?\s*\{"""
    )
    RE_TYPE = re.compile(
        r"""(?:export\s+)?type\s+(\w+)"""
    )
    RE_FUNCTION = re.compile(
        r"""(?:export\s+)?(?:async\s+)?function\s+(\w+)"""
    )
    RE_CONST_FUNC = re.compile(
        r"""(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\("""
    )
    RE_ROUTE = re.compile(
        r"""(?:app|router)\.(?:get|post|put|delete|patch|route)\s*\(['"]([^'"]+)['"]"""
    )
    RE_REACT_COMPONENT = re.compile(
        r"""(?:export\s+)?(?:default\s+)?function\s+([A-Z]\w+)"""
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
            imp = m.group(1) or m.group(2)
            if imp and not imp.startswith("."):
                result.imports.append(imp)
            elif imp:
                resolved = self._resolve_relative(imp, file_path, root)
                if resolved:
                    result.relationships.append(Relationship(
                        source=file_id, target=resolved, type="imports",
                        confidence="EXTRACTED", evidence=f"import {imp}",
                    ))

        # Classes
        for m in self.RE_CLASS.finditer(content):
            name = m.group(1)
            extends = m.group(2)
            implements = self._parse_list(m.group(3))
            result.entities.append(Entity(
                id=name, type="class", name=name, file=file_id,
                line=self._line_of(content, m.start()),
            ))
            if extends:
                result.relationships.append(Relationship(
                    source=name, target=extends, type="extends",
                    confidence="EXTRACTED",
                ))
            for impl in implements:
                result.relationships.append(Relationship(
                    source=name, target=impl.strip(), type="implements",
                    confidence="EXTRACTED",
                ))

        # Interfaces
        for m in self.RE_INTERFACE.finditer(content):
            name = m.group(1)
            extends = self._parse_list(m.group(2))
            result.entities.append(Entity(
                id=name, type="class", name=name, file=file_id,
                line=self._line_of(content, m.start()),
                metadata={"kind": "interface"},
            ))
            for ext in extends:
                result.relationships.append(Relationship(
                    source=name, target=ext.strip(), type="extends",
                    confidence="EXTRACTED",
                ))

        # Type aliases
        for m in self.RE_TYPE.finditer(content):
            result.entities.append(Entity(
                id=m.group(1), type="schema", name=m.group(1), file=file_id,
                line=self._line_of(content, m.start()),
            ))

        # Functions
        for m in self.RE_FUNCTION.finditer(content):
            result.entities.append(Entity(
                id=m.group(1), type="function", name=m.group(1), file=file_id,
                line=self._line_of(content, m.start()),
            ))

        # Const arrow functions
        for m in self.RE_CONST_FUNC.finditer(content):
            name = m.group(1)
            if name[0].isupper():
                result.entities.append(Entity(
                    id=name, type="class", name=name, file=file_id,
                    line=self._line_of(content, m.start()),
                    metadata={"kind": "component"},
                ))
            else:
                result.entities.append(Entity(
                    id=name, type="function", name=name, file=file_id,
                    line=self._line_of(content, m.start()),
                ))

        # Routes
        for m in self.RE_ROUTE.finditer(content):
            path = m.group(1)
            result.entities.append(Entity(
                id=f"route:{path}", type="route", name=path, file=file_id,
                line=self._line_of(content, m.start()),
            ))

        return result

    def _resolve_relative(self, imp: str, file_path: Path, root: Path) -> str:
        resolved = (file_path.parent / imp).resolve()
        for ext in ["", ".js", ".ts", ".jsx", ".tsx", "/index.js", "/index.ts"]:
            candidate = resolved.with_suffix("") if ext else resolved
            if ext:
                candidate = resolved.parent / (resolved.name + ext)
            if candidate.exists():
                try:
                    return str(candidate.relative_to(root))
                except ValueError:
                    return str(candidate)
        return None

    def _parse_list(self, s: str) -> list:
        if not s:
            return []
        return [x.strip() for x in s.split(",") if x.strip()]

    def _line_of(self, content: str, pos: int) -> int:
        return content[:pos].count("\n") + 1
