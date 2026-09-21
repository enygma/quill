"""Filesystem-backed storage for Quill notes."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .models import Note

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    slug = SLUG_RE.sub("-", title.strip().lower()).strip("-")
    return slug or "note"


class NoteNotFoundError(Exception):
    pass


class NoteStore:
    """CRUD + listing operations over Markdown note files on disk."""

    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        # Resolve once so it stays consistent with the resolved paths
        # _abs_path() produces (important on systems where the root sits
        # under a symlink, e.g. macOS's /tmp -> /private/tmp).
        self.root = root.resolve()

    # -- path helpers ---------------------------------------------------

    def _abs_path(self, rel_path: str) -> Path:
        return (self.root / f"{rel_path}.md").resolve()

    def _unique_rel_path(self, folder: str, slug: str) -> str:
        base = f"{folder}/{slug}" if folder else slug
        candidate = base
        n = 2
        while self._abs_path(candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        return candidate

    # -- listing ----------------------------------------------------------

    def list_notes(self) -> list[Note]:
        notes: list[Note] = []
        for path in sorted(self.root.rglob("*.md")):
            if path.name.startswith("."):
                continue
            try:
                notes.append(Note.from_file(path, self.root))
            except Exception:
                continue
        return notes

    def list_folders(self) -> list[str]:
        folders: set[str] = set()
        for path in self.root.rglob("*"):
            if path.is_dir():
                folders.add(path.relative_to(self.root).as_posix())
        return sorted(folders)

    def create_folder(self, folder: str) -> str:
        """Create an empty folder (for organizing notes) and return its
        rel-path. Safe to call on a folder that already exists."""
        folder = folder.strip("/")
        (self.root / folder).mkdir(parents=True, exist_ok=True)
        return folder

    def rename_folder(self, folder: str, new_name: str) -> str:
        """Rename a folder's last path segment in place (moving it and
        everything inside it). Returns the new folder rel-path."""
        folder = folder.strip("/")
        if not folder:
            raise ValueError("Can't rename the top-level notes directory.")
        old_abs = self.root / folder
        if not old_abs.is_dir():
            raise FileNotFoundError(f"No such folder: {folder}")

        parent = "/".join(folder.split("/")[:-1])
        new_slug = slugify(new_name)
        new_folder = f"{parent}/{new_slug}" if parent else new_slug
        new_abs = self.root / new_folder
        if new_abs.exists():
            raise FileExistsError(f"A folder already exists at: {new_folder}")

        new_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_abs), str(new_abs))
        return new_folder

    # -- CRUD ---------------------------------------------------------------

    def get(self, rel_path: str) -> Note:
        path = self._abs_path(rel_path)
        if not path.exists():
            raise NoteNotFoundError(rel_path)
        return Note.from_file(path, self.root)

    def create(
        self,
        title: str,
        body: str = "",
        folder: str = "",
        pinned: bool = False,
        tags: list[str] | None = None,
    ) -> Note:
        folder = folder.strip("/")
        slug = slugify(title)
        rel_path = self._unique_rel_path(folder, slug)
        abs_path = self._abs_path(rel_path)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        note = Note(
            path=abs_path,
            rel_path=rel_path,
            title=title,
            body=body,
            pinned=pinned,
            tags=tags or [],
        )
        abs_path.write_text(note.to_markdown(), encoding="utf-8")
        return note

    def save(self, note: Note, touch: bool = True) -> Note:
        if touch:
            note.touch()
        note.path.parent.mkdir(parents=True, exist_ok=True)
        note.path.write_text(note.to_markdown(), encoding="utf-8")
        return note

    def rename(self, note: Note, new_title: str) -> Note:
        old_path = note.path
        folder = note.folder
        new_slug = slugify(new_title)
        new_rel = self._unique_rel_path(folder, new_slug) if new_slug != old_path.stem else note.rel_path
        new_abs = self._abs_path(new_rel)
        note.title = new_title
        note.rel_path = new_rel
        note.path = new_abs
        self.save(note)
        if old_path.exists() and old_path != new_abs:
            old_path.unlink()
        return note

    def delete(self, rel_path: str) -> None:
        path = self._abs_path(rel_path)
        if not path.exists():
            raise NoteNotFoundError(rel_path)
        path.unlink()
        # Clean up now-empty parent directories, but never remove the root.
        parent = path.parent
        while parent != self.root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    def toggle_pin(self, rel_path: str) -> Note:
        note = self.get(rel_path)
        note.pinned = not note.pinned
        return self.save(note, touch=False)

    def move(self, note: Note, new_folder: str) -> Note:
        new_folder = new_folder.strip("/")
        new_rel = self._unique_rel_path(new_folder, slugify(note.title))
        old_path = note.path
        new_abs = self._abs_path(new_rel)
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_path), str(new_abs))
        note.rel_path = new_rel
        note.path = new_abs
        return note

    # -- wiki-link resolution -------------------------------------------

    def resolve_link(self, target: str) -> Note | None:
        """Resolve a [[wiki link]] target to a Note by title or rel_path."""
        target_norm = target.strip().lower()
        for note in self.list_notes():
            if note.title.strip().lower() == target_norm:
                return note
            if note.rel_path.lower() == target_norm:
                return note
        return None
