"""Builds the dashboard shown in preview when no note is open: pending
tasks across all notes, and notes that haven't been touched in a while.

Generates plain Markdown using Quill's own checklist ('- [ ]') and
wiki-link ('[[Title]]') conventions, so it renders and navigates through
the exact same pipeline as a real note -- checkmarks, clickable links, 'g'
to jump to one -- with no special-casing needed.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from .models import Note, parse_dt
from .storage import NoteStore

_UNCHECKED_TASK_RE = re.compile(r"^\s*-\s\[\s\]\s+(.+)$", re.MULTILINE)

STALE_DAYS = 30
MAX_PENDING_TASKS = 15
MAX_STALE_NOTES = 10

WELCOME_HEADER = "# Welcome to Quill"
WELCOME_HINT = "Select a note from the sidebar, or press `n` to create a new one."


def _pending_tasks(notes: list[Note]) -> list[tuple[str, str]]:
    """(note_title, task_text) for every unchecked checklist item, in
    sidebar order (folder, then title)."""
    tasks = []
    for note in notes:
        for match in _UNCHECKED_TASK_RE.finditer(note.body):
            text = match.group(1).strip()
            if text:
                tasks.append((note.title, text))
    return tasks


def _stale_notes(notes: list[Note], days: int) -> list[tuple[Note, datetime]]:
    cutoff = datetime.now() - timedelta(days=days)
    stale = []
    for note in notes:
        updated = parse_dt(note.updated)
        if updated is not None and updated < cutoff:
            stale.append((note, updated))
    stale.sort(key=lambda pair: pair[1])  # oldest first
    return stale


def build_welcome_markdown(store: NoteStore, stale_days: int = STALE_DAYS) -> str:
    notes = store.list_notes()
    if not notes:
        return f"{WELCOME_HEADER}\n\n{WELCOME_HINT}\n"

    lines = [WELCOME_HEADER, ""]

    tasks = _pending_tasks(notes)
    lines.append(f"## Pending tasks ({len(tasks)})")
    lines.append("")
    if tasks:
        for title, text in tasks[:MAX_PENDING_TASKS]:
            lines.append(f"- [ ] {text} ([[{title}]])")
        if len(tasks) > MAX_PENDING_TASKS:
            lines.append(f"- *...and {len(tasks) - MAX_PENDING_TASKS} more*")
    else:
        lines.append("*Nothing pending.*")
    lines.append("")

    stale = _stale_notes(notes, stale_days)
    lines.append(f"## Notes untouched for {stale_days}+ days")
    lines.append("")
    if stale:
        for note, updated in stale[:MAX_STALE_NOTES]:
            lines.append(f"- [[{note.title}]] *(last updated {updated:%Y-%m-%d})*")
        if len(stale) > MAX_STALE_NOTES:
            lines.append(f"- *...and {len(stale) - MAX_STALE_NOTES} more*")
    else:
        lines.append("*Everything's been touched recently.*")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(WELCOME_HINT)

    return "\n".join(lines)
