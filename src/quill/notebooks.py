"""Notebooks: independent top-level groupings of notes.

Each notebook is its own directory under the configured notes_dir, with its
own folder structure, Templates folder, and revision history -- distinct
from a regular folder *within* a notebook, which is just for organizing
notes inside that one notebook.
"""

from __future__ import annotations

import shutil
from pathlib import Path

DEFAULT_NOTEBOOK = "Default"

# Marks a notes_dir as already migrated (or never having needed it), so the
# one-time legacy migration below never runs more than once, regardless of
# what notebooks a user creates, renames, or empties afterward.
_MIGRATION_MARKER = ".notebooks"


def notebook_path(notes_dir: Path, notebook: str) -> Path:
    return notes_dir / notebook


def list_notebooks(notes_dir: Path) -> list[str]:
    if not notes_dir.is_dir():
        return []
    return sorted(p.name for p in notes_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def ensure_notebook(notes_dir: Path, notebook: str) -> Path:
    """Create the notebook's directory if it doesn't exist yet, and return its path."""
    path = notebook_path(notes_dir, notebook)
    path.mkdir(parents=True, exist_ok=True)
    return path


def migrate_legacy_notes(notes_dir: Path) -> None:
    """One-time migration: if `notes_dir` predates notebooks -- its notes,
    folders, Templates, and history all sit directly inside it -- move
    everything into a Default notebook instead. Safe to call on every
    startup; only actually does anything the first time for a given
    notes_dir, marked by a hidden file so it's never re-triggered even if
    that Default notebook is later renamed or emptied out.
    """
    notes_dir.mkdir(parents=True, exist_ok=True)
    marker = notes_dir / _MIGRATION_MARKER
    if marker.exists():
        return

    default_dir = notes_dir / DEFAULT_NOTEBOOK
    existing = [p for p in notes_dir.iterdir() if p.name != _MIGRATION_MARKER and p != default_dir]
    if existing:
        default_dir.mkdir(exist_ok=True)
        for item in existing:
            shutil.move(str(item), str(default_dir / item.name))

    marker.touch()
