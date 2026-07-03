"""Extract raw instruction text from code files.

Handles:
- Dart triple-quoted strings (''' ... ''')
- Python docstrings and triple-quoted strings
- JavaScript/TypeScript template literals
- Markdown files (raw text)
- YAML/JSON config files with instruction content
"""

import re
from pathlib import Path
from typing import List, Optional


class PromptExtractor:
    """Extract instruction text from various file types."""

    # File extensions that are pure instruction text (no code wrapping)
    PURE_TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".prompt", ".instructions"}

    # File extensions that may contain embedded instructions
    CODE_EXTENSIONS = {
        ".dart", ".py", ".js", ".jsx", ".ts", ".tsx",
        ".yaml", ".yml", ".json", ".toml",
    }

    # Patterns for extracting strings from code
    PATTERNS = {
        # Dart triple-quoted strings: '''...''' or """..."""
        "dart_triple": re.compile(
            r"('''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\")",
            re.MULTILINE,
        ),
        # Dart string literals (single/double quoted, multi-line via +)
        "dart_strings": re.compile(
            r"(?:const\s+)?(?:String\s+\w+\s*=>?\s*)?(['\"])(.*?)\1",
            re.DOTALL,
        ),
        # Python docstrings
        "python_docstring": re.compile(
            r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')',
            re.MULTILINE,
        ),
        # JS/TS template literals
        "js_template": re.compile(
            r"(`[\s\S]*?`)",
            re.MULTILINE,
        ),
        # YAML string values (multiline with | or >)
        "yaml_multiline": re.compile(
            r"^(\w[\w\s]*):\s*(\|[\s\S]*?|>[\s\S]*?)(?=\n\w|\Z)",
            re.MULTILINE,
        ),
    }

    # Minimum chunk size to consider (avoids extracting tiny fragments)
    MIN_CHUNK_LENGTH = 50

    def extract(self, file_path: Path) -> Optional[str]:
        """Extract instruction text from a file.

        Returns the full extractable text content, or None if no
        instruction-bearing content found.
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        suffix = file_path.suffix.lower()

        if suffix in self.PURE_TEXT_EXTENSIONS:
            return content.strip()

        if suffix == ".dart":
            return self._extract_dart(content)

        if suffix == ".py":
            return self._extract_python(content)

        if suffix in (".js", ".jsx", ".ts", ".tsx"):
            return self._extract_javascript(content)

        if suffix in (".yaml", ".yml"):
            return self._extract_yaml(content)

        if suffix == ".json":
            return self._extract_json(content)

        return None

    def extract_chunks(self, file_path: Path) -> List[str]:
        """Extract individual instruction text chunks from a file.

        Returns a list of separate text blocks found in the file.
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        suffix = file_path.suffix.lower()

        if suffix in self.PURE_TEXT_EXTENSIONS:
            # Split markdown by headers or double newlines
            return self._split_markdown(content)

        if suffix == ".dart":
            return self._extract_dart_chunks(content)

        if suffix == ".py":
            return self._extract_python_chunks(content)

        if suffix in (".js", ".jsx", ".ts", ".tsx"):
            return self._extract_js_chunks(content)

        return []

    def _extract_dart(self, content: str) -> Optional[str]:
        """Extract instruction text from Dart triple-quoted strings."""
        matches = self.PATTERNS["dart_triple"].findall(content)
        # Filter out small matches (likely not instructions)
        texts = [m.strip("'").strip('"').strip() for m in matches if len(m) > self.MIN_CHUNK_LENGTH]
        return "\n\n".join(texts) if texts else None

    def _extract_dart_chunks(self, content: str) -> List[str]:
        """Extract individual Dart string chunks."""
        matches = self.PATTERNS["dart_triple"].findall(content)
        texts = [m.strip("'").strip('"').strip() for m in matches if len(m) > self.MIN_CHUNK_LENGTH]
        return texts

    def _extract_python(self, content: str) -> Optional[str]:
        """Extract instruction text from Python docstrings."""
        matches = self.PATTERNS["python_docstring"].findall(content)
        texts = [m.strip('"').strip("'").strip() for m in matches if len(m) > self.MIN_CHUNK_LENGTH]
        return "\n\n".join(texts) if texts else None

    def _extract_python_chunks(self, content: str) -> List[str]:
        """Extract individual Python docstring chunks."""
        matches = self.PATTERNS["python_docstring"].findall(content)
        texts = [m.strip('"').strip("'").strip() for m in matches if len(m) > self.MIN_CHUNK_LENGTH]
        return texts

    def _extract_javascript(self, content: str) -> Optional[str]:
        """Extract instruction text from JS/TS template literals."""
        matches = self.PATTERNS["js_template"].findall(content)
        texts = [m.strip("`").strip() for m in matches if len(m) > self.MIN_CHUNK_LENGTH]
        return "\n\n".join(texts) if texts else None

    def _extract_js_chunks(self, content: str) -> List[str]:
        """Extract individual JS/TS template literal chunks."""
        matches = self.PATTERNS["js_template"].findall(content)
        texts = [m.strip("`").strip() for m in matches if len(m) > self.MIN_CHUNK_LENGTH]
        return texts

    def _extract_yaml(self, content: str) -> Optional[str]:
        """Extract instruction text from YAML multiline strings."""
        matches = self.PATTERNS["yaml_multiline"].findall(content)
        texts = []
        for key, val in matches:
            cleaned = re.sub(r"^\s*\|\s*\n?", "", val, flags=re.MULTILINE).strip()
            if len(cleaned) > self.MIN_CHUNK_LENGTH:
                texts.append(cleaned)
        return "\n\n".join(texts) if texts else None

    def _extract_json(self, content: str) -> Optional[str]:
        """Extract instruction text from JSON string values."""
        import json
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None

        texts = []
        self._extract_json_strings(data, texts)
        return "\n\n".join(t for t in texts if len(t) > self.MIN_CHUNK_LENGTH) or None

    def _extract_json_strings(self, obj, texts: List[str]):
        """Recursively extract string values from JSON."""
        if isinstance(obj, str) and len(obj) > self.MIN_CHUNK_LENGTH:
            texts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._extract_json_strings(v, texts)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_json_strings(item, texts)

    def _split_markdown(self, content: str) -> List[str]:
        """Split markdown content into meaningful chunks by headers."""
        chunks = []
        current_chunk = []
        current_header = ""

        for line in content.split("\n"):
            if re.match(r"^#{1,3}\s+", line):
                if current_chunk:
                    text = "\n".join(current_chunk).strip()
                    if len(text) > self.MIN_CHUNK_LENGTH:
                        chunks.append(text)
                current_header = line
                current_chunk = [line]
            else:
                current_chunk.append(line)

        if current_chunk:
            text = "\n".join(current_chunk).strip()
            if len(text) > self.MIN_CHUNK_LENGTH:
                chunks.append(text)

        return chunks if chunks else [content.strip()]
