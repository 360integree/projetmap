"""Generic extractor — fallback for unsupported languages."""

import re
from pathlib import Path

from codemap.extractors.base import BaseExtractor, Entity, ExtractionResult, Relationship


class GenericExtractor(BaseExtractor):
    """Generic regex-based extractor for any source file."""

    RE_IMPORT = re.compile(
        r"""(?:import|include|require|use)\s+['"<]([^'">]+)['">]"""
    )
    RE_CLASS = re.compile(
        r"""(?:class|struct|interface|trait|type|record)\s+(\w+)"""
    )
    RE_FUNCTION = re.compile(
        r"""(?:function|def|fn|func|sub|procedure|method)\s+(\w+)"""
    )

    def extract(self, file_path: Path, root: Path) -> ExtractionResult:
        content = self._read_file(file_path)
        if not content:
            return ExtractionResult()

        result = ExtractionResult()
        file_id = self._file_id(file_path, root)

        result.entities.append(Entity(
            id=file_id, type="module", name=file_path.name, file=file_id,
            metadata={"lines": len(content.split("\n")), "ext": file_path.suffix},
        ))

        for m in self.RE_IMPORT.finditer(content):
            result.imports.append(m.group(1))

        for m in self.RE_CLASS.finditer(content):
            result.entities.append(Entity(
                id=m.group(1), type="class", name=m.group(1), file=file_id,
            ))

        for m in self.RE_FUNCTION.finditer(content):
            name = m.group(1)
            if len(name) > 2:
                result.entities.append(Entity(
                    id=name, type="function", name=name, file=file_id,
                ))

        return result
