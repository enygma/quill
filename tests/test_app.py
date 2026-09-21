from pathlib import Path

import pytest

from quill.app import QuillApp
from quill.config import AIConfig, QuillConfig
from quill.widgets.ai_panel import AIPanel
from quill.widgets.editor import NoteEditor
from quill.widgets.modals import HelpModal
from quill.widgets.preview import NotePreview, WikiLinkActivated
from quill.widgets.sidebar import Sidebar


@pytest.fixture
def config(tmp_path: Path) -> QuillConfig:
    return QuillConfig(notes_dir=tmp_path / "notes", ai=AIConfig(enabled=False))


@pytest.mark.asyncio
async def test_select_edit_save_and_checkbox_toggle(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Grocery List", body="- [ ] Milk\n- [ ] Eggs", pinned=True)

    async with app.run_test() as pilot:
        await pilot.pause()
        sidebar = app.query_one(Sidebar)
        sidebar.focus()
        await pilot.press("down")  # highlights the "Pinned" section header
        await pilot.press("down")  # highlights the note itself
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.rel_path == "grocery-list"

        await pilot.press("e")
        await pilot.pause()
        assert app.editing is True

        app.query_one(NoteEditor).toggle_checkbox_on_current_line()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.editing is False
        assert app.current_note.body.splitlines()[0] == "- [x] Milk"


@pytest.mark.asyncio
async def test_new_note_flow(config: QuillConfig) -> None:
    app = QuillApp(config)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press(*"My New Note")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.title == "My New Note"
        assert app.editing is True  # new notes open straight into edit mode


@pytest.mark.asyncio
async def test_delete_requires_confirmation(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("Delete Me")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()

        # Cancel (default focus) leaves the note intact.
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.store.list_notes() != []

        # Confirm (Tab to the Delete button) removes it.
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()
        assert app.store.list_notes() == []


@pytest.mark.asyncio
async def test_pin_toggle(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("Pin Me")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.press("p")
        await pilot.pause()
        assert app.current_note.pinned is True


@pytest.mark.asyncio
async def test_search_enter_opens_top_result(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Grocery List")
    app.store.create("Trip Plan")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        for ch in "Grocery":
            await pilot.press(ch)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.title == "Grocery List"


@pytest.mark.asyncio
async def test_wikilink_activation_opens_target(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Target Note")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(WikiLinkActivated("Target Note"))
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.title == "Target Note"


@pytest.mark.asyncio
async def test_ai_panel_toggle_and_escape_closes_it(tmp_path: Path) -> None:
    # Needs the 'a' shortcut enabled (it's hidden/disabled when ai.enabled=False).
    config = QuillConfig(notes_dir=tmp_path / "notes", ai=AIConfig(enabled=True))
    app = QuillApp(config)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        panel = app.query_one(AIPanel)
        assert panel.has_class("-visible")

        # 'a' now types into the focused chat input rather than re-toggling;
        # Escape is the reliable way to close it.
        await pilot.press("escape")
        await pilot.pause()
        assert not panel.has_class("-visible")
        assert app.focused is app.query_one(Sidebar)


@pytest.mark.asyncio
async def test_settings_change_swaps_notes_dir(config: QuillConfig, tmp_path: Path) -> None:
    from textual.widgets import Input

    from quill.widgets.modals import SettingsModal

    app = QuillApp(config)
    new_dir = tmp_path / "elsewhere"
    async with app.run_test(size=(120, 60)) as pilot:
        await pilot.pause()
        old_store = app.store
        await pilot.press("s")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsModal)
        screen.query_one("#notes-dir-input", Input).value = str(new_dir)
        await pilot.click("#save")
        await pilot.pause()
        assert app.store is not old_store
        assert app.config.notes_dir == new_dir


@pytest.mark.asyncio
async def test_help_modal_opens_and_closes(config: QuillConfig) -> None:
    app = QuillApp(config)
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpModal)


@pytest.mark.asyncio
async def test_ai_footer_shortcut_hidden_when_disabled(config: QuillConfig) -> None:
    # `config` fixture has ai.enabled=False.
    app = QuillApp(config)
    async with app.run_test() as pilot:
        await pilot.pause()
        actions = {b.binding.action for b in app.active_bindings.values()}
        assert "toggle_ai" not in actions

        # The key does nothing while the shortcut is hidden/disabled.
        await pilot.press("a")
        await pilot.pause()
        assert not app.query_one(AIPanel).has_class("-visible")


@pytest.mark.asyncio
async def test_ai_footer_shortcut_shown_when_enabled(tmp_path: Path) -> None:
    config = QuillConfig(notes_dir=tmp_path / "notes", ai=AIConfig(enabled=True))
    app = QuillApp(config)
    async with app.run_test() as pilot:
        await pilot.pause()
        actions = {b.binding.action for b in app.active_bindings.values()}
        assert "toggle_ai" in actions

        await pilot.press("a")
        await pilot.pause()
        assert app.query_one(AIPanel).has_class("-visible")


@pytest.mark.asyncio
async def test_ai_footer_shortcut_updates_live_from_settings(config: QuillConfig) -> None:
    from textual.widgets import Switch

    from quill.widgets.modals import SettingsModal

    app = QuillApp(config)
    async with app.run_test(size=(120, 65)) as pilot:
        await pilot.pause()
        assert "toggle_ai" not in {b.binding.action for b in app.active_bindings.values()}

        await pilot.press("s")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsModal)
        screen.query_one("#ai-enabled-switch", Switch).value = True
        await pilot.click("#save")
        await pilot.pause()

        assert "toggle_ai" in {b.binding.action for b in app.active_bindings.values()}
