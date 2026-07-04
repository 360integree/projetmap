"""SHA256-based caching for incremental graph updates."""

import hashlib
import json
from pathlib import Path


def file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cache(cache_dir: Path) -> dict[str, str]:
    """Load file hash cache."""
    cache_file = cache_dir / "file_hashes.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return {}


def save_cache(cache_dir: Path, hashes: dict[str, str]) -> None:
    """Save file hash cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "file_hashes.json"
    with open(cache_file, "w") as f:
        json.dump(hashes, f, indent=2)


def get_changed_files(
    files: list[Path], cache_dir: Path, root: Path
) -> tuple[list[Path], dict[str, str]]:
    """Compare file hashes to find changed files. Returns (changed, new_hashes)."""
    old_hashes = load_cache(cache_dir)
    new_hashes = {}
    changed = []

    for f in files:
        rel = str(f.relative_to(root))
        h = file_hash(f)
        new_hashes[rel] = h
        if rel not in old_hashes or old_hashes[rel] != h:
            changed.append(f)

    return changed, new_hashes


def get_cached_graph(output_dir: Path) -> dict | None:
    """Load cached graph.json if it exists."""
    graph_file = output_dir / "graph.json"
    if graph_file.exists():
        with open(graph_file) as f:
            return json.load(f)
    return None


def save_graph(output_dir: Path, graph: dict) -> None:
    """Save graph to graph.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "graph.json", "w") as f:
        json.dump(graph, f, indent=2)
