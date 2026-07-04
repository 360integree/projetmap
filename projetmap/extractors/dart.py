"""Dart/Flutter extractor — regex-based AST parsing."""

import re
from pathlib import Path

from projetmap.extractors.base import BaseExtractor, Entity, ExtractionResult, Relationship


class DartExtractor(BaseExtractor):
    """Extract entities and relationships from Dart/Flutter files."""

    # Patterns
    RE_IMPORT = re.compile(r"""(?:import|export)\s+['"]([^'"]+)['"]""")
    RE_PART = re.compile(r"""part\s+['"]([^'"]+)['"]""")
    RE_CLASS = re.compile(
        r"""(?:abstract\s+|sealed\s+|final\s+)?class\s+(\w+)(?:\s*<[^>]+>)?"""
        r"""(?:\s+extends\s+(\w+))?"""
        r"""(?:\s+with\s+([\w\s,]+?))?"""
        r"""(?:\s+implements\s+([\w\s,]+?))?"""
        r"""\s*\{"""
    )
    RE_MIXIN = re.compile(
        r"""mixin\s+(\w+)(?:\s+on\s+([\w\s,]+?))?\s*\{"""
    )
    RE_ENUM = re.compile(
        r"""enum\s+(\w+)(?:\s+with\s+([\w\s,]+?))?\s*\{"""
    )
    RE_FUNCTION = re.compile(
        r"""(?:static\s+)?(?:Future|Stream|void|String|int|double|bool|dynamic|List|Map|Set|Iterable)\s*<?[\w,\s>]*>?\s+(\w+)\s*\("""
    )
    RE路由 = re.compile(
        r"""GoRoute\s*\(\s*(?:path:\s*['"]([^'"]+)['"]|name:\s*['"]([^'"]+)['"])"""
    )
    RE_PROVIDER = re.compile(
        r"""(?:StateProvider|FutureProvider|StreamProvider|NotifierProvider|AsyncNotifierProvider|Provider)\s*<[^>]*>\s*\(\s*(?:[\w.]*\s*(?:ref|read|watch)\s*(?:\.\w+)?\s*(?:=>\s*[^;]+)?)"""
    )
    RE_PROVIDER_DECL = re.compile(
        r"""(\w+Provider)\s*=\s*(?:StateProvider|FutureProvider|StreamProvider|NotifierProvider|AsyncNotifierProvider)"""
    )
    RE_TABLE = re.compile(
        r"""class\s+(\w+)\s+extends\s+Table"""
    )
    RE_COLUMN = re.compile(
        r"""(?:TextColumn|IntColumn|RealColumn|BoolColumn|DateTimeColumn|BlobColumn)\s+get\s+(\w+)"""
    )
    RE_FREEZED = re.compile(r"""@freezed|@Freezed\(|@JsonSerializable""")
    RE_OVERRIDE = re.compile(r"""@override""")
    RE_TOOL = re.compile(
        r"""class\s+(\w+)\s+extends\s+(?:Base)?Tool"""
    )
    RE_FACTORY = re.compile(
        r"""factory\s+(\w+)\s*\("""
    )

    def extract(self, file_path: Path, root: Path) -> ExtractionResult:
        content = self._read_file(file_path)
        if not content:
            return ExtractionResult()

        result = ExtractionResult()
        file_id = self._file_id(file_path, root)
        lines = content.split("\n")

        # File module entity
        result.entities.append(Entity(
            id=file_id,
            type="module",
            name=file_path.name,
            file=file_id,
            metadata={"lines": len(lines), "ext": file_path.suffix},
        ))

        # Extract imports
        for m in self.RE_IMPORT.finditer(content):
            imp = m.group(1)
            result.imports.append(imp)
            target = self._resolve_import(imp, file_path, root)
            if target:
                result.relationships.append(Relationship(
                    source=file_id,
                    target=target,
                    type="imports",
                    confidence="EXTRACTED",
                    evidence=f"import statement: {imp}",
                ))

        # Extract parts
        for m in self.RE_PART.finditer(content):
            part = m.group(1)
            target = self._resolve_import(part, file_path, root)
            if target:
                result.relationships.append(Relationship(
                    source=file_id,
                    target=target,
                    type="imports",
                    confidence="EXTRACTED",
                    evidence=f"part directive: {part}",
                ))

        # Extract classes
        for m in self.RE_CLASS.finditer(content):
            name = m.group(1)
            extends = m.group(2)
            withs = self._parse_list(m.group(3))
            implements = self._parse_list(m.group(4))

            result.entities.append(Entity(
                id=name,
                type="class",
                name=name,
                file=file_id,
                line=self._line_of(content, m.start()),
                metadata=self._class_metadata(content, m.start(), name),
            ))

            if extends:
                result.relationships.append(Relationship(
                    source=name, target=extends, type="extends",
                    confidence="EXTRACTED",
                    evidence=f"class {name} extends {extends}",
                ))
            for w in withs:
                result.relationships.append(Relationship(
                    source=name, target=w.strip(), type="implements",
                    confidence="EXTRACTED",
                    evidence=f"class {name} with {w.strip()}",
                ))
            for i in implements:
                result.relationships.append(Relationship(
                    source=name, target=i.strip(), type="implements",
                    confidence="EXTRACTED",
                    evidence=f"class {name} implements {i.strip()}",
                ))

        # Extract mixins
        for m in self.RE_MIXIN.finditer(content):
            name = m.group(1)
            on_types = self._parse_list(m.group(2))
            result.entities.append(Entity(
                id=name, type="mixin", name=name, file=file_id,
                line=self._line_of(content, m.start()),
            ))
            for ot in on_types:
                result.relationships.append(Relationship(
                    source=name, target=ot.strip(), type="implements",
                    confidence="EXTRACTED",
                    evidence=f"mixin {name} on {ot.strip()}",
                ))

        # Extract enums
        for m in self.RE_ENUM.finditer(content):
            name = m.group(1)
            result.entities.append(Entity(
                id=name, type="enum", name=name, file=file_id,
                line=self._line_of(content, m.start()),
            ))

        # Extract functions (top-level and class methods)
        for m in self.RE_FUNCTION.finditer(content):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "return", "import", "class"):
                continue
            result.entities.append(Entity(
                id=name, type="function", name=name, file=file_id,
                line=self._line_of(content, m.start()),
            ))

        # Extract GoRouter routes
        for m in self.RE路由.finditer(content):
            path = m.group(1) or m.group(2)
            if path:
                result.entities.append(Entity(
                    id=f"route:{path}", type="route", name=path, file=file_id,
                    line=self._line_of(content, m.start()),
                ))

        # Extract Riverpod providers
        for m in self.RE_PROVIDER_DECL.finditer(content):
            name = m.group(1)
            result.entities.append(Entity(
                id=name, type="config", name=name, file=file_id,
                line=self._line_of(content, m.start()),
                metadata={"kind": "riverpod_provider"},
            ))

        # Extract Drift tables
        for m in self.RE_TABLE.finditer(content):
            name = m.group(1)
            result.entities.append(Entity(
                id=name, type="schema", name=name, file=file_id,
                line=self._line_of(content, m.start()),
                metadata={"kind": "drift_table"},
            ))

        # Extract freezed models
        if self.RE_FREEZED.search(content):
            for m in self.RE_CLASS.finditer(content):
                name = m.group(1)
                for ent in result.entities:
                    if ent.id == name and ent.type == "class":
                        ent.metadata["source"] = "freezed"
                        break

        # Extract tool classes
        for m in self.RE_TOOL.finditer(content):
            name = m.group(1)
            for ent in result.entities:
                if ent.id == name and ent.type == "class":
                    ent.metadata["kind"] = "tool"
                    break

        # Extract internal function calls (basic heuristic)
        self._extract_calls(content, result, file_id)

        return result

    def _resolve_import(self, imp: str, file_path: Path, root: Path) -> str:
        """Resolve import path to a file ID."""
        if imp.startswith("dart:"):
            return None
        if imp.startswith("package:"):
            parts = imp.split("/")
            if len(parts) >= 3:
                pkg = parts[1]
                sub = "/".join(parts[2:])
                # Try to find in packages/ or lib/
                for base in [root / "packages" / pkg / "lib", root / "lib"]:
                    candidate = base / sub
                    if candidate.exists():
                        try:
                            return str(candidate.relative_to(root))
                        except ValueError:
                            return str(candidate)
                return f"{pkg}/{sub}"
        if imp.startswith("../") or imp.startswith("./"):
            resolved = (file_path.parent / imp).resolve()
            try:
                return str(resolved.relative_to(root))
            except ValueError:
                return str(resolved)
        return None

    def _parse_list(self, s: str) -> list[str]:
        """Parse comma-separated list of identifiers."""
        if not s:
            return []
        return [x.strip() for x in s.split(",") if x.strip()]

    def _line_of(self, content: str, pos: int) -> int:
        """Get line number for a position in content."""
        return content[:pos].count("\n") + 1

    def _class_metadata(self, content: str, pos: int, name: str) -> dict:
        """Extract metadata about a class."""
        meta = {}
        # Check what comes before the class declaration
        prefix = content[max(0, pos - 200):pos]
        if "@immutable" in prefix:
            meta["immutable"] = True
        if "abstract" in prefix.split("class")[0][-20:]:
            meta["abstract"] = True
        return meta

    def _extract_calls(self, content: str, result: ExtractionResult, file_id: str):
        """Extract function call relationships (heuristic)."""
        # Find all entity names defined in this file
        entity_names = {e.name for e in result.entities if e.type in ("class", "function")}
        # Simple heuristic: if entity name appears as word boundary in content
        for name in entity_names:
            call_pattern = re.compile(r'\b' + re.escape(name) + r'\s*\(')
            for m in call_pattern.finditer(content):
                line = self._line_of(content, m.start())
                # Don't add self-references
                result.relationships.append(Relationship(
                    source=file_id,
                    target=name,
                    type="calls",
                    confidence="INFERRED",
                    evidence=f"{name}() called in {file_id}",
                    line=line,
                ))
