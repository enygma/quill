from pathlib import Path

import pytest

from quill.app import QuillApp
from quill.config import AIConfig, QuillConfig
from quill.widgets.ai_panel import AIPanel
from quill.widgets.editor import NoteEditor
from quill.widgets.modals import HelpModal, LinkPickerModal
from quill.widgets.preview import LinkActivated
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
async def test_wikilink_autocomplete_accept_with_enter(config: QuillConfig) -> None:
    # Regression test: TextArea consumes Enter itself (inserting a newline)
    # before it would normally bubble to NoteEditor's key handling, so
    # accepting a wiki-link suggestion with Enter silently did nothing and
    # left the note with a broken, unclosed "[[..." link instead.
    app = QuillApp(config)
    app.store.create("Project Alpha notes")
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()

        for ch in "See [[Proj":
            await pilot.press(ch)
        await pilot.pause()

        editor = app.query_one(NoteEditor)
        assert editor.suggestions_visible

        await pilot.press("enter")
        await pilot.pause()
        assert editor.text == "See [[Project Alpha notes]]"

        # Enter still inserts a normal newline once there's no suggestion open.
        await pilot.press("enter")
        await pilot.pause()
        assert editor.text == "See [[Project Alpha notes]]\n"


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
        app.post_message(LinkActivated("Target Note"))
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
async def test_help_modal_does_not_wrap_on_a_wide_terminal(config: QuillConfig) -> None:
    from quill.widgets.modals import HELP_SECTIONS

    app = QuillApp(config)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        sections = list(app.screen.query(".help-section"))
        for (_, rows), widget in zip(HELP_SECTIONS, sections):
            expected_lines = 1 + len(rows)  # section title + one line per row
            assert widget.region.height == expected_lines


@pytest.mark.asyncio
async def test_help_modal_wraps_and_shrinks_on_a_narrow_terminal(config: QuillConfig) -> None:
    app = QuillApp(config)
    async with app.run_test(size=(60, 50)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        box = app.screen.query_one("#help-box")
        assert box.region.width < 60


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


@pytest.mark.asyncio
async def test_go_to_link_single_link_jumps_directly(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Target One")
    single = app.store.create("Single Linker", body="See [[Target One]] for details.")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(single.rel_path)
        await pilot.pause()
        await pilot.press("g")
        # Regression test: refresh_sidebar()'s programmatic cursor move used
        # to race with the sidebar's own async NodeHighlighted message and
        # get silently reverted back to whatever note was previously open.
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.title == "Target One"


@pytest.mark.asyncio
async def test_go_to_link_multiple_links_shows_picker(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Target One")
    app.store.create("Target Two")
    multi = app.store.create("Multi Linker", body="See [[Target One]] and [[Target Two|the second]].")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(multi.rel_path)
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        assert isinstance(app.screen, LinkPickerModal)

        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_note.title == "Target Two"


@pytest.mark.asyncio
async def test_go_to_link_no_links_warns_without_crashing(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("No Links Here", body="Just plain text.")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        assert app.current_note.title == "No Links Here"


@pytest.mark.asyncio
async def test_go_to_link_regular_markdown_link(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Other Note")
    src = app.store.create("Source", body="Check the [markdown link](Other Note) for details.")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(src.rel_path)
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        assert app.current_note.title == "Other Note"


@pytest.mark.asyncio
async def test_go_to_link_url_opens_browser(config: QuillConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    import webbrowser

    opened = {}
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.setdefault("url", url))

    app = QuillApp(config)
    note = app.store.create("Has URL", body="See [docs](https://example.com/page) here.")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        assert opened.get("url") == "https://example.com/page"
        assert app.current_note.title == "Has URL"  # unchanged; nothing to open in-app


@pytest.mark.asyncio
async def test_sidebar_pinned_header_always_visible(config: QuillConfig) -> None:
    app = QuillApp(config)
    async with app.run_test() as pilot:
        await pilot.pause()
        sidebar = app.query_one(Sidebar)
        labels = [str(n.label) for n in sidebar.root.children]
        assert labels[0] == "📌 Pinned"  # present with zero notes at all

        app.store.create("Unpinned Note")
        app.refresh_sidebar()
        await pilot.pause()
        labels = [str(n.label) for n in sidebar.root.children]
        assert labels[0] == "📌 Pinned"  # still first with notes, none pinned


@pytest.mark.asyncio
async def test_move_note_via_folder_autocomplete(config: QuillConfig) -> None:
    from quill.widgets.folder_input import FolderInput
    from quill.widgets.modals import MoveNoteModal

    app = QuillApp(config)
    note = app.store.create("Grocery List", folder="personal")
    app.store.create_folder("work/projects")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, MoveNoteModal)
        assert app.screen.query_one(FolderInput).value == "personal"

        inp = app.screen.query_one("#move-folder-input")
        inp.value = ""
        await pilot.pause()
        for ch in "work/proj":
            await pilot.press(ch)
        await pilot.pause()
        assert app.screen.query_one("#move-folder-input-suggestions").display

        await pilot.press("enter")  # accept the suggestion
        await pilot.pause()
        assert app.screen.query_one("#move-folder-input").value == "work/projects"

        await pilot.press("enter")  # submit the modal
        await pilot.pause()
        assert app.current_note.folder == "work/projects"
        assert app.current_note.rel_path == "work/projects/grocery-list"


@pytest.mark.asyncio
async def test_rename_note(config: QuillConfig) -> None:
    from quill.widgets.modals import RenameModal

    app = QuillApp(config)
    note = app.store.create("Old Title", folder="projects")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, RenameModal)
        app.screen.query_one("#rename-input").value = "New Title"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_note.title == "New Title"
        assert app.current_note.rel_path == "projects/new-title"


@pytest.mark.asyncio
async def test_rename_folder_via_sidebar(config: QuillConfig) -> None:
    from quill.widgets.modals import RenameModal

    app = QuillApp(config)
    app.store.create("A Note", folder="projects")

    async with app.run_test() as pilot:
        await pilot.pause()
        sidebar = app.query_one(Sidebar)
        sidebar.focus()
        await pilot.press("down")  # Pinned header
        await pilot.press("down")  # projects folder
        await pilot.pause()
        assert Sidebar.folder_for(sidebar.cursor_node) == "projects"

        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, RenameModal)
        app.screen.query_one("#rename-input").value = "work stuff"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.store.list_folders() == ["work-stuff"]
        assert app.store.get("work-stuff/a-note").title == "A Note"


@pytest.mark.asyncio
async def test_new_note_defaults_to_sidebar_highlighted_folder(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Existing", folder="projects")

    async with app.run_test() as pilot:
        await pilot.pause()
        sidebar = app.query_one(Sidebar)
        sidebar.focus()
        await pilot.press("down")  # Pinned header
        await pilot.press("down")  # projects folder
        await pilot.pause()
        assert Sidebar.folder_for(sidebar.cursor_node) == "projects"

        await pilot.press("n")
        await pilot.pause()
        from quill.widgets.folder_input import FolderInput

        assert app.screen.query_one(FolderInput).value == "projects"
