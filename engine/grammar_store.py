"""Grammar storage utilities for preset discovery and loading."""

from __future__ import annotations

import json
from pathlib import Path


def _grammar_files(grammar_dir: Path) -> dict[str, Path]:
    """Map preset names to JSON files discovered under grammar_dir."""
    return {
        path.stem: path
        for path in grammar_dir.glob("*.json")
        if path.stem != "schema"
    }


def list_grammar_names(grammar_dir: Path) -> list[str]:
    """Return sorted preset names from the grammar directory."""
    return sorted(_grammar_files(grammar_dir))


def load_grammar(grammar_dir: Path, name: str) -> dict:
    """Load a grammar by name from `<grammar_dir>/<name>.json`."""
    path = _grammar_files(grammar_dir).get(name)
    if path is None:
        raise FileNotFoundError(f"Grammar '{name}' not found")
    return json.loads(path.read_text())
