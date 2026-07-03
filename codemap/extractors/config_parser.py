"""Config file parser — extracts project metadata from pubspec.yaml, package.json, etc."""

import json
from pathlib import Path
from typing import Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None


def parse_config(file_path: Path) -> Optional[Dict]:
    """Parse a config file and return metadata."""
    if file_path.name == "pubspec.yaml":
        return _parse_pubspec(file_path)
    elif file_path.name == "package.json":
        return _parse_package_json(file_path)
    elif file_path.name == "pyproject.toml":
        return _parse_pyproject(file_path)
    return None


def _parse_pubspec(file_path: Path) -> Optional[Dict]:
    if yaml is None:
        return None
    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
        if not data:
            return None
        name = data.get("name", "unknown")
        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("dev_dependencies", {}).keys())
        return {
            "name": name,
            "type": "flutter_package" if "flutter" in deps else "dart_package",
            "dependencies": deps,
            "dev_dependencies": dev_deps,
            "flutter": "flutter" in deps,
        }
    except Exception:
        return None


def _parse_package_json(file_path: Path) -> Optional[Dict]:
    try:
        with open(file_path) as f:
            data = json.load(f)
        name = data.get("name", "unknown")
        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("devDependencies", {}).keys())
        scripts = list(data.get("scripts", {}).keys())
        return {
            "name": name,
            "type": "node_package",
            "dependencies": deps,
            "dev_dependencies": dev_deps,
            "scripts": scripts,
        }
    except Exception:
        return None


def _parse_pyproject(file_path: Path) -> Optional[Dict]:
    try:
        content = file_path.read_text()
        # Simple TOML-like parsing for [project] section
        name = "unknown"
        for line in content.split("\n"):
            if line.strip().startswith("name"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    name = parts[1].strip().strip('"').strip("'")
                    break
        return {"name": name, "type": "python_package"}
    except Exception:
        return None
