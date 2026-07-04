"""Shared utility functions for codemap."""

import os
from pathlib import Path


def get_project_root(start: str = ".") -> Path:
    """Find project root by looking for common markers."""
    p = Path(start).resolve()
    markers = [
        "pubspec.yaml", "package.json", "pyproject.toml", "Cargo.toml",
        "go.mod", "pom.xml", "build.gradle", ".git",
    ]
    for parent in [p, *p.parents]:
        for marker in markers:
            if (parent / marker).exists():
                return parent
    return p


def should_ignore(path: Path, ignore_patterns: list[str], root: Path) -> bool:
    """Check if a path should be ignored."""
    rel = str(path.relative_to(root))
    default_ignores = {
        ".git", "node_modules", "__pycache__", ".dart_tool", "build",
        ".gradle", ".idea", "venv", ".venv", "dist", "target",
        "*.g.dart", "*.freezed.dart", "*.mocks.dart", "*.gr.dart",
    }
    patterns = set(ignore_patterns) | default_ignores
    for pattern in patterns:
        if pattern.startswith("*"):
            if rel.endswith(pattern[1:]):
                return True
        elif pattern in rel.split(os.sep):
            return True
        elif rel.startswith(pattern):
            return True
    return False


def collect_files(
    root: Path,
    scan_dirs: list[str] = None,
    ignore_patterns: list[str] = None,
) -> list[Path]:
    """Collect all source files in the project."""
    if ignore_patterns is None:
        ignore_patterns = []

    extensions = {
        ".dart", ".py", ".js", ".jsx", ".ts", ".tsx",
        ".java", ".go", ".rs", ".rb", ".php", ".cs",
        ".swift", ".kt", ".scala", ".clj", ".ex", ".exs",
        ".sql", ".sh", ".bash", ".zsh",
    }

    files = []
    search_dirs = [root] if not scan_dirs else [
        root / d for d in scan_dirs if (root / d).exists()
    ]

    for search_dir in search_dirs:
        for path in search_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in extensions:
                continue
            if should_ignore(path, ignore_patterns, root):
                continue
            files.append(path)

    return sorted(files)


def entity_id(name: str, file_path: str, root: Path) -> str:
    """Generate a stable entity ID."""
    return name


def truncate(s: str, max_len: int = 80) -> str:
    """Truncate string with ellipsis."""
    return s if len(s) <= max_len else s[:max_len - 3] + "..."


def relative_path(path: Path, root: Path) -> str:
    """Get relative path string."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
