from pathlib import Path

import pytest

import quill.history as history_module
from quill.storage import NoteStore


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests want to control exactly when a snapshot is taken; the real
    # 5-minute floor would make that require sleeping in tests.
    monkeypatch.setattr(history_module, "MIN_SNAPSHOT_GAP_SECONDS", 0)


def test_no_revision_on_create(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", body="v1")
    assert store.list_revisions(note.rel_path) == []


def test_save_snapshots_the_previous_version(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", body="v1")
    note.body = "v2"
    store.save(note)
    revisions = store.list_revisions(note.rel_path)
    assert len(revisions) == 1
    assert revisions[0].body == "v1"
    assert store.get(note.rel_path).body == "v2"


def test_revisions_pruned_to_max_revisions(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=3)
    note = store.create("Test", body="v1")
    for body in ["v2", "v3", "v4", "v5"]:
        note.body = body
        store.save(note)
    revisions = store.list_revisions(note.rel_path)
    # max_revisions counts the current on-disk version, so 2 old snapshots kept.
    assert [r.body for r in revisions] == ["v3", "v4"]
    assert store.get(note.rel_path).body == "v5"


def test_history_disabled_takes_no_snapshots(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=False, max_revisions=5)
    note = store.create("Test", body="v1")
    note.body = "v2"
    store.save(note)
    assert store.list_revisions(note.rel_path) == []


def test_snapshot_throttled_without_the_fixture_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(history_module, "MIN_SNAPSHOT_GAP_SECONDS", 300)
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", body="v1")
    note.body = "v2"
    store.save(note)
    note.body = "v3"
    store.save(note)  # immediately after -> should be throttled, no second snapshot
    revisions = store.list_revisions(note.rel_path)
    assert len(revisions) == 1
    assert revisions[0].body == "v1"


def test_restore_snapshots_current_state_first(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", body="v1")
    note.body = "v2"
    store.save(note)

    revisions = store.list_revisions(note.rel_path)
    restored = store.restore_revision(note, revisions[0])

    assert restored.body == "v1"
    assert store.get(note.rel_path).body == "v1"
    # The pre-restore state ("v2") is preserved as a new revision.
    after = store.list_revisions(note.rel_path)
    assert [r.body for r in after] == ["v1", "v2"]


def test_restore_is_not_throttled_by_a_recent_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # snapshot_now() (used by restore) must bypass the throttle -- it's a
    # safety net, not a routine save, and must never be silently skipped.
    monkeypatch.setattr(history_module, "MIN_SNAPSHOT_GAP_SECONDS", 300)
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", body="v1")
    note.body = "v2"
    store.save(note)  # first snapshot ("v1"), starts the throttle window

    revisions = store.list_revisions(note.rel_path)
    store.restore_revision(note, revisions[0])  # would be throttled if save()'s path were used

    after = store.list_revisions(note.rel_path)
    assert [r.body for r in after] == ["v1", "v2"]


def test_two_restores_in_immediate_succession_both_snapshot(tmp_path: Path) -> None:
    # Regression test: snapshot filenames used second-level timestamp
    # precision, so two snapshot_now() calls landing in the same second
    # collided and the second one was silently dropped.
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", body="v1")
    note.body = "v2"
    store.save(note)
    note.body = "v3"
    store.save(note)

    revisions = store.list_revisions(note.rel_path)
    assert [r.body for r in revisions] == ["v1", "v2"]

    restored = store.restore_revision(note, revisions[0])  # restore "v1"
    restored.body = "v4"
    restored2 = store.restore_revision(restored, store.list_revisions(note.rel_path)[0])
    assert restored2 is not None
    # Both restores' pre-restore states should be captured, not dropped.
    bodies = [r.body for r in store.list_revisions(note.rel_path)]
    assert len(bodies) >= 2


def test_history_hidden_from_list_notes_and_list_folders(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", folder="projects", body="v1")
    note.body = "v2"
    store.save(note)

    assert all(".history" not in n.rel_path for n in store.list_notes())
    assert all(".history" not in f for f in store.list_folders())
    assert len(store.list_revisions(note.rel_path)) == 1  # sanity: history really was created


def test_rename_keeps_history_attached(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Original Title", body="v1")
    note.body = "v2"
    store.save(note)

    renamed = store.rename(note, "New Title")
    assert len(store.list_revisions(renamed.rel_path)) == 1
    assert store.list_revisions("original-title") == []


def test_move_keeps_history_attached(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", body="v1")
    note.body = "v2"
    store.save(note)

    moved = store.move(note, "somewhere")
    assert len(store.list_revisions(moved.rel_path)) == 1


def test_rename_folder_keeps_history_attached(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", folder="projects", body="v1")
    note.body = "v2"
    store.save(note)

    new_folder = store.rename_folder("projects", "work stuff")
    moved_rel = f"{new_folder}/test"
    assert len(store.list_revisions(moved_rel)) == 1


def test_delete_removes_history(tmp_path: Path) -> None:
    store = NoteStore(tmp_path, history_enabled=True, max_revisions=5)
    note = store.create("Test", body="v1")
    note.body = "v2"
    store.save(note)
    assert len(store.list_revisions(note.rel_path)) == 1

    store.delete(note.rel_path)
    assert store.list_revisions(note.rel_path) == []
