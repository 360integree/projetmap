"""Pluggable behavioral extractors per language.

Each language extractor must produce a behavioral_data.json conforming
to the schema documented in SCHEMA.md.

To add a new language:
1. Create a directory: behavioral/extractors/<language>/
2. Add an extractor script/program that outputs behavioral_data.json
3. Register it in DETECTORS below
"""
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# Map: language name -> (detector function, extractor runner)
DETECTORS = {}


def _detect_dart(root: Path) -> bool:
    """Detect Dart projects by presence of pubspec.yaml (root or monorepo subdirs)."""
    if (root / "pubspec.yaml").exists():
        return True
    # Monorepo: check apps/* and packages/*
    for subdir in ["apps", "packages"]:
        search_dir = root / subdir
        if search_dir.exists():
            for child in search_dir.iterdir():
                if (child / "pubspec.yaml").exists():
                    return True
    return False


def _run_dart_extractor(root: Path, output_path: str) -> bool:
    """Run the Dart AST behavioral extractor."""
    extractor_dir = Path(__file__).parent / "dart"
    extractor_script = extractor_dir / "dart_behavioral_extractor.dart"

    if not extractor_script.exists():
        return False

    try:
        result = subprocess.run(
            ["dart", "run", str(extractor_script), str(root), output_path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(extractor_dir),
        )
        if result.returncode != 0:
            print(f"  ❌ Dart extractor failed: {result.stderr}")
            return False
        print(f"  {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("  ❌ 'dart' command not found. Ensure Dart SDK is in PATH.")
        return False
    except subprocess.TimeoutExpired:
        print("  ❌ Dart extractor timed out (120s limit).")
        return False


# Register Dart
DETECTORS["dart"] = (_detect_dart, _run_dart_extractor)

# To add more languages, register here:
# DETECTORS["python"] = (_detect_python, _run_python_extractor)
# DETECTORS["javascript"] = (_detect_js, _run_js_extractor)


def detect_language(root: Path) -> str | None:
    """Detect the project language and return the matching extractor name."""
    for lang, (detector, _) in DETECTORS.items():
        if detector(root):
            return lang
    return None


def run_extractor(language: str, root: Path, output_path: str) -> bool:
    """Run the behavioral extractor for the given language."""
    if language not in DETECTORS:
        return False
    _, runner = DETECTORS[language]
    return runner(root, output_path)
