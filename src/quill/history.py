"""Simple timestamped revision history for notes.

Not git -- just enough to get back a recent version of a note without
leaving the app. Snapshots live in a hidden `.history/` folder at the notes
root, mirroring the note's own rel_path, and are pruned to a configured max
count (which includes the current on-disk version).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

HISTORY_FOLDER = ".history"
# Microsecond precision: snapshot_now() is meant to *guarantee* a snapshot
# is taken (it backs the safety-net copy made just before a restore), so
# two calls landing in the same second must not collide and silently drop
# one -- with only second-level precision they did.
_TIMESTAMP_FMT = "%Y%m%dT%H%M%S%f"

# Snapshots are only taken on save() -- which autosave calls every few
# seconds while actively typing -- so without a floor a single editing
# session would burn through the whole revision cap in well under a
# minute. This keeps snapshots meaningfully spread out in time instead.
MIN_SNAPSHOT_GAP_SECONDS = 5 * 60


@dataclass
class Revision:
    rel_path: str
    timestamp: datetime
    path: Path

    @property
    def body(self) -> str:
        text = self.path.read_text(encoding="utf-8")
        # Revisions are saved as a full copy of the note file (frontmatter
        # included); callers generally want just the body, matching Note.body.
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                return text[end + 5 :].strip("\n")
        return text


class RevisionStore:
    def __init__(self, root: Path):
        self.root = root

    def _history_dir_for(self, rel_path: str) -> Path:
        return self.root / HISTORY_FOLDER / rel_path

    def list_revisions(self, rel_path: str) -> list[Revision]:
        """Existing revisions for a note, oldest first."""
        history_dir = self._history_dir_for(rel_path)
        if not history_dir.is_dir():
            return []
        revisions = []
        for path in sorted(history_dir.glob("*.md")):
            try:
                timestamp = datetime.strptime(path.stem, _TIMESTAMP_FMT)
            except ValueError:
                continue
            revisions.append(Revision(rel_path=rel_path, timestamp=timestamp, path=path))
        return revisions

    def maybe_snapshot(self, rel_path: str, current_abs_path: Path, max_revisions: int) -> None:
        """If `current_abs_path` holds a previous version worth keeping and
        enough time has passed since the last snapshot, copy it into history
        before it gets overwritten, then prune to `max_revisions`."""
        if max_revisions < 1 or not current_abs_path.exists():
            return
        revisions = self.list_revisions(rel_path)
        if revisions:
            elapsed = (datetime.now() - revisions[-1].timestamp).total_seconds()
            if elapsed < MIN_SNAPSHOT_GAP_SECONDS:
                return
        self._snapshot_now(rel_path, current_abs_path, max_revisions)

    def snapshot_now(self, rel_path: str, current_abs_path: Path, max_revisions: int) -> None:
        """Unconditionally snapshot, ignoring the throttle window -- used
        before a restore, so the pre-restore state is never silently lost
        even if a recent autosave-driven snapshot already exists."""
        if max_revisions < 1 or not current_abs_path.exists():
            return
        self._snapshot_now(rel_path, current_abs_path, max_revisions)

    def _snapshot_now(self, rel_path: str, current_abs_path: Path, max_revisions: int) -> None:
        history_dir = self._history_dir_for(rel_path)
        history_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime(_TIMESTAMP_FMT)
        shutil.copy2(current_abs_path, history_dir / f"{stamp}.md")
        self._prune(rel_path, max_revisions)

    def _prune(self, rel_path: str, max_revisions: int) -> None:
        keep = max(max_revisions - 1, 0)  # the on-disk note itself counts toward the cap
        revisions = self.list_revisions(rel_path)
        excess = len(revisions) - keep
        for old in revisions[: max(excess, 0)]:
            old.path.unlink(missing_ok=True)

    def delete_history(self, rel_path: str) -> None:
        history_dir = self._history_dir_for(rel_path)
        if history_dir.is_dir():
            shutil.rmtree(history_dir)

    def rename_history(self, old_rel_path: str, new_rel_path: str) -> None:
        """Keep a note's revision history attached to it across a rename/move."""
        old_dir = self._history_dir_for(old_rel_path)
        if not old_dir.is_dir():
            return
        new_dir = self._history_dir_for(new_rel_path)
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_dir), str(new_dir))

    def rename_history_folder(self, old_folder: str, new_folder: str) -> None:
        """Keep a whole folder's worth of notes' history attached across a
        folder rename (NoteStore.rename_folder moves everything at once)."""
        old_dir = self.root / HISTORY_FOLDER / old_folder
        if not old_dir.is_dir():
            return
        new_dir = self.root / HISTORY_FOLDER / new_folder
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_dir), str(new_dir))
