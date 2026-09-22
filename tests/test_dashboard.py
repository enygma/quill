from datetime import datetime, timedelta
from pathlib import Path

from quill.dashboard import WELCOME_HINT, build_welcome_markdown
from quill.storage import NoteStore


def _backdate(store: NoteStore, note, days: int) -> None:
    note.updated = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    store.save(note, touch=False)


def test_empty_store_shows_plain_welcome(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    markdown = build_welcome_markdown(store)
    assert "# Welcome to Quill" in markdown
    assert WELCOME_HINT in markdown
    assert "Pending tasks" not in markdown


def test_pending_tasks_collected_across_notes(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create("Note A", body="- [ ] Task one\n- [x] Done already")
    store.create("Note B", body="- [ ] Task two")

    markdown = build_welcome_markdown(store)
    assert "## Pending tasks (2)" in markdown
    assert "Task one ([[Note A]])" in markdown
    assert "Task two ([[Note B]])" in markdown
    assert "Done already" not in markdown  # checked items aren't "pending"


def test_no_pending_tasks_shows_friendly_message(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create("Note", body="- [x] All done\nJust prose.")
    markdown = build_welcome_markdown(store)
    assert "*Nothing pending.*" in markdown


def test_stale_notes_listed_oldest_first(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create("Fresh Note")
    old = store.create("Old Note")
    older = store.create("Older Note")
    _backdate(store, old, days=35)
    _backdate(store, older, days=90)

    markdown = build_welcome_markdown(store, stale_days=30)
    assert "Fresh Note" not in markdown.split("## Notes untouched")[1]
    older_idx = markdown.index("Older Note")
    old_idx = markdown.index("[[Old Note]]")
    assert older_idx < old_idx  # older one listed first


def test_notes_within_the_threshold_are_not_stale(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    note = store.create("Recent Note")
    _backdate(store, note, days=10)
    markdown = build_welcome_markdown(store, stale_days=30)
    assert "*Everything's been touched recently.*" in markdown


def test_pending_tasks_capped_with_overflow_message(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    body = "\n".join(f"- [ ] Task {i}" for i in range(20))
    store.create("Busy Note", body=body)
    markdown = build_welcome_markdown(store)
    assert "## Pending tasks (20)" in markdown
    assert "*...and 5 more*" in markdown


def test_stale_notes_capped_with_overflow_message(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    for i in range(12):
        note = store.create(f"Note {i}")
        _backdate(store, note, days=40)
    markdown = build_welcome_markdown(store, stale_days=30)
    assert "*...and 2 more*" in markdown


def test_dedupes_a_note_appearing_in_both_sections(tmp_path: Path) -> None:
    # A note can have both a pending task and be stale -- the wiki-link
    # itself only needs to be unique per find_link_targets, but each
    # section's own listing should still show it once per occurrence type.
    store = NoteStore(tmp_path)
    note = store.create("Busy And Old", body="- [ ] Still pending")
    _backdate(store, note, days=60)
    markdown = build_welcome_markdown(store, stale_days=30)
    assert markdown.count("[[Busy And Old]]") == 2  # once per section, that's expected
