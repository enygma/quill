from pathlib import Path

import pytest

from quill.app import QuillApp
from quill.config import AIConfig, QuillConfig
from quill.widgets.ai_panel import AIPanel
from quill.widgets.editor import NoteEditor
from quill.widgets.modals import ConfirmModal, HelpModal, LinkPickerModal
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
    async with app.run_test(size=(120, 70)) as pilot:
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
async def test_help_modal_shortcuts_section_does_not_wrap(tmp_path: Path) -> None:
    # The dynamic Shortcuts section isn't in the static HELP_SECTIONS list,
    # so the test above never actually checks its sizing -- verify separately.
    config = QuillConfig(notes_dir=tmp_path / "notes", ai=AIConfig(enabled=False), shortcuts={"sig": "Best,\nSomeone"})
    app = QuillApp(config)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        shortcuts_section = list(app.screen.query(".help-section"))[-1]
        assert "Shortcuts" in str(shortcuts_section.render())
        assert shortcuts_section.region.height == 4  # title + 2 builtins + 1 custom


@pytest.mark.asyncio
async def test_help_modal_does_not_leak_literal_markup_tags(config: QuillConfig) -> None:
    # Regression test: entries containing a literal '[' (the "[[" wiki-link
    # key, and "'- [ ]'" in the ctrl+t entry) confused Textual's Content
    # markup parser -- distinct from, and stricter than, Rich's own
    # Text.from_markup -- causing a literal "[/b]" to leak into the
    # rendered text instead of being consumed as the closing bold tag.
    app = QuillApp(config)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        rendered = "\n".join(str(s.render()) for s in app.screen.query(".help-section"))
        assert "[/b]" not in rendered
        assert "[[" in rendered  # the literal content itself still shows up
        assert "'- [ ]'" in rendered


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
    async with app.run_test(size=(120, 70)) as pilot:
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

        # 'Templates' is auto-created by the app on mount.
        assert set(app.store.list_folders()) == {"work-stuff", "Templates"}
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


@pytest.mark.asyncio
async def test_broken_wikilink_shows_banner_and_is_not_clickable(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Real Note")
    src = app.store.create("Source", body="See [[Real Note]] and [[Ghost Note]] here.")
    clean = app.store.create("Clean Note", body="No links here at all.")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(src.rel_path)
        await pilot.pause()

        banner = app.query_one("#broken-links-banner")
        assert banner.has_class("-visible")
        assert "Ghost Note" in str(banner.render())

        md = app.query_one("#preview-markdown")
        assert "wiki:Real" in md.source  # working link stays a real, clickable link
        assert "wiki:Ghost" not in md.source  # broken one is not rendered as a link
        assert "Ghost Note" in md.source  # but the label is still visible

        # A note with no broken links shows no banner.
        app.open_note(clean.rel_path)
        await pilot.pause()
        assert not banner.has_class("-visible")

        # 'g' still finds it via the raw [[Ghost Note]] text (independent of
        # rendering) and reports it's missing, same as any other bad link.
        app.open_note(src.rel_path)
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        from quill.widgets.modals import LinkPickerModal

        assert isinstance(app.screen, LinkPickerModal)
        await pilot.press("down")  # Real Note, then Ghost Note
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_note.title == "Source"  # nothing to navigate to


@pytest.mark.asyncio
async def test_breadcrumb_shows_folder_path_and_survives_edit_mode(config: QuillConfig) -> None:
    from textual.widgets import Static

    app = QuillApp(config)
    top_note = app.store.create("Ambiguous Title")
    nested_note = app.store.create("Ambiguous Title", folder="projects/work")

    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one("#breadcrumb-bar", Static)

        app.open_note(top_note.rel_path)
        await pilot.pause()
        assert str(bar.render()) == "Ambiguous Title"

        app.open_note(nested_note.rel_path)
        await pilot.pause()
        assert str(bar.render()) == "projects › work › Ambiguous Title"

        app.action_edit_note()
        await pilot.pause()
        assert str(bar.render()) == "projects › work › Ambiguous Title"

        app.current_note = None
        app._show_preview(None)
        await pilot.pause()
        assert str(bar.render()) == ""


@pytest.mark.asyncio
async def test_preview_shows_checkmarks_but_saved_file_keeps_gfm_syntax(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("Todo", body="- [ ] Buy milk\n- [x] Walk the dog")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        md = app.query_one("#preview-markdown")
        assert "✅ Walk the dog" in md.source
        assert "☐ Buy milk" in md.source
        assert "[x]" not in md.source
        # The rendering is preview-only; the file on disk stays standard GFM.
        assert app.store.get(note.rel_path).body == "- [ ] Buy milk\n- [x] Walk the dog"


@pytest.mark.asyncio
async def test_templates_folder_auto_created_on_startup(config: QuillConfig) -> None:
    from quill.storage import TEMPLATES_FOLDER

    app = QuillApp(config)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert TEMPLATES_FOLDER in app.store.list_folders()


@pytest.mark.asyncio
async def test_insert_template_requires_editing(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Standup", folder="Templates", body="Yesterday:\nToday:")
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        # Not editing -> ctrl+g is a no-op (with a notification), no modal.
        await pilot.press("ctrl+g")
        await pilot.pause()
        from quill.widgets.modals import InsertTemplateModal

        assert not isinstance(app.screen, InsertTemplateModal)


@pytest.mark.asyncio
async def test_insert_template_with_none_available_warns(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        await pilot.press("ctrl+g")
        await pilot.pause()
        from quill.widgets.modals import InsertTemplateModal

        assert not isinstance(app.screen, InsertTemplateModal)


@pytest.mark.asyncio
async def test_insert_template_narrows_and_inserts_at_cursor(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Meeting Notes", folder="Templates", body="## Attendees")
    app.store.create("Daily Standup", folder="Templates", body="Yesterday:\nToday:\nBlockers:")
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()

        editor = app.query_one(NoteEditor)
        area = editor.query_one("#editor-textarea")
        area.load_text("before|after")
        area.move_cursor((0, 6))
        await pilot.pause()

        await pilot.press("ctrl+g")
        await pilot.pause()
        from quill.widgets.modals import InsertTemplateModal

        assert isinstance(app.screen, InsertTemplateModal)

        for ch in "Stand":
            await pilot.press(ch)
        await pilot.pause()
        results = app.screen.query_one("#template-results")
        assert len(results.children) == 1  # narrowed to just "Daily Standup"

        await pilot.press("enter")
        await pilot.pause()

        assert editor.text == "beforeYesterday:\nToday:\nBlockers:|after"
        assert app.editing is True  # stays in edit mode, doesn't exit
        # Inserting into the editor doesn't touch the saved file.
        assert app.store.get(note.rel_path).body == ""


def test_default_save_mode_is_manual() -> None:
    from quill.config import QuillConfig as PlainQuillConfig

    assert PlainQuillConfig(notes_dir=Path("/nonexistent")).save_mode == "manual"


@pytest.mark.asyncio
async def test_escape_with_no_changes_discards_immediately(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("A Note", body="original")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.editing is False
        assert not isinstance(app.screen, ConfirmModal)


@pytest.mark.asyncio
async def test_escape_with_unsaved_changes_prompts_before_discarding(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("A Note", body="original")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        editor = app.query_one(NoteEditor)
        editor.query_one("#editor-textarea").insert("X")
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        assert app.editing is True  # unchanged until a choice is made

        # Cancel keeps the edit and the unsaved text.
        await pilot.press("enter")  # default focus is Cancel
        await pilot.pause()
        assert app.editing is True
        assert editor.text == "Xoriginal"

        # Escape again, this time confirm -> discards back to the saved version.
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()
        assert app.editing is False
        assert app.store.get(note.rel_path).body == "original"


@pytest.mark.asyncio
async def test_view_history_with_none_yet_warns(config: QuillConfig) -> None:
    from quill.widgets.modals import HistoryModal

    app = QuillApp(config)
    note = app.store.create("A Note", body="v1")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("h")
        await pilot.pause()
        assert not isinstance(app.screen, HistoryModal)


@pytest.mark.asyncio
async def test_view_and_restore_history(config: QuillConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    import quill.history as history_module
    from quill.widgets.modals import HistoryModal

    monkeypatch.setattr(history_module, "MIN_SNAPSHOT_GAP_SECONDS", 0)

    app = QuillApp(config)
    note = app.store.create("A Note", body="version one")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()

        app.action_edit_note()
        await pilot.pause()
        area = app.query_one(NoteEditor).query_one("#editor-textarea")
        area.load_text("version two")
        await pilot.press("ctrl+s")
        await pilot.pause()

        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.screen, HistoryModal)

        await pilot.press("enter")  # only one revision -> restore it directly
        await pilot.pause()

        assert app.current_note.body == "version one"
        assert app.store.get(note.rel_path).body == "version one"
        # The pre-restore state ("version two") is preserved, not lost.
        assert [r.body for r in app.store.list_revisions(note.rel_path)] == ["version one", "version two"]


@pytest.mark.asyncio
async def test_default_notebook_created_on_startup(tmp_path: Path) -> None:
    config = QuillConfig(notes_dir=tmp_path / "notes", ai=AIConfig(enabled=False))
    app = QuillApp(config)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.notebook == "Default"
        assert (tmp_path / "notes" / "Default").is_dir()
        assert app.title == "Quill: Default"


@pytest.mark.asyncio
async def test_open_notebook_creates_and_switches(config: QuillConfig) -> None:
    from quill.widgets.modals import OpenNotebookModal

    app = QuillApp(config)
    app.store.create("Default's Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()
        assert isinstance(app.screen, OpenNotebookModal)
        for ch in "Work":
            await pilot.press(ch)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.notebook == "Work"
        assert app.title == "Quill: Work"
        assert app.store.list_notes() == []  # fresh, separate notebook
        assert app.config.current_notebook == "Work"


@pytest.mark.asyncio
async def test_open_notebook_switches_back_and_forth_keeping_notes_separate(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Default's Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()
        for ch in "Work":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        app.store.create("Work's Note")

        await pilot.press("o")
        await pilot.pause()
        for ch in "Default":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app.notebook == "Default"
        assert [n.title for n in app.store.list_notes()] == ["Default's Note"]


@pytest.mark.asyncio
async def test_open_notebook_plain_o_types_into_the_note_while_editing(config: QuillConfig) -> None:
    # Regression test: 'o' is a plain letter, swallowed as text by the
    # editor, so it must never reach action_open_notebook while editing.
    from quill.widgets.modals import OpenNotebookModal

    app = QuillApp(config)
    note = app.store.create("A Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()

        await pilot.press("o")
        await pilot.pause()
        assert not isinstance(app.screen, OpenNotebookModal)
        editor = app.query_one(NoteEditor)
        assert "o" in editor.text  # the letter was typed into the note instead


@pytest.mark.asyncio
async def test_open_notebook_ctrl_o_reachable_while_editing(config: QuillConfig) -> None:
    # ctrl+o is the alias that must work mid-edit, unlike plain 'o'.
    from quill.widgets.modals import OpenNotebookModal

    app = QuillApp(config)
    note = app.store.create("A Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()  # no changes made -> no unsaved-changes prompt in the way
        await pilot.pause()

        await pilot.press("ctrl+o")
        await pilot.pause()
        assert isinstance(app.screen, OpenNotebookModal)


@pytest.mark.asyncio
async def test_open_notebook_prompts_for_unsaved_changes(config: QuillConfig) -> None:
    from quill.widgets.modals import ConfirmModal, OpenNotebookModal

    app = QuillApp(config)
    note = app.store.create("A Note", body="original")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        editor = app.query_one(NoteEditor)
        editor.query_one("#editor-textarea").insert("X")
        await pilot.pause()

        await pilot.press("ctrl+o")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        assert app.notebook == "Default"  # unchanged until a choice is made

        # Cancel -> stays on the same notebook, edit untouched.
        await pilot.press("enter")  # default focus is Cancel
        await pilot.pause()
        assert app.notebook == "Default"
        assert app.editing is True
        assert editor.text == "Xoriginal"

        # Confirm -> switches, discarding the unsaved edit.
        await pilot.press("ctrl+o")
        await pilot.pause()
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, OpenNotebookModal)
        for ch in "Work":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app.notebook == "Work"
        # The unsaved edit was never written to the Default notebook's file.
        from quill.storage import NoteStore

        default_store = NoteStore(config.notes_dir / "Default")
        assert default_store.get(note.rel_path).body == "original"


@pytest.mark.asyncio
async def test_notebooks_have_independent_templates_and_history(config: QuillConfig) -> None:
    app = QuillApp(config)

    async with app.run_test() as pilot:
        await pilot.pause()
        app.store.create("Default Template", folder="Templates")

        await pilot.press("o")
        await pilot.pause()
        for ch in "Work":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app.store.list_templates() == []  # Work's Templates folder is separate


@pytest.mark.asyncio
async def test_welcome_dashboard_shown_at_startup(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("A Note", body="- [ ] Something to do")

    async with app.run_test() as pilot:
        await pilot.pause()
        md = app.query_one("#preview-markdown")
        assert "Pending tasks (1)" in md.source
        assert "Something to do" in md.source


@pytest.mark.asyncio
async def test_welcome_dashboard_link_click_navigates(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Target Note", body="- [ ] A task")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(LinkActivated("Target Note"))
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.title == "Target Note"


@pytest.mark.asyncio
async def test_welcome_dashboard_g_navigates(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Only Task Note", body="- [ ] A single task")

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.current_note is None
        await pilot.press("g")
        await pilot.pause()
        # Exactly one unique link on the dashboard -> jumps directly.
        assert app.current_note is not None
        assert app.current_note.title == "Only Task Note"


@pytest.mark.asyncio
async def test_welcome_dashboard_refreshes_after_returning_to_it(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Stays Around")  # keeps the store non-empty after the delete below
    note = app.store.create("Will Be Deleted", body="- [ ] Doomed task")

    async with app.run_test() as pilot:
        await pilot.pause()
        md = app.query_one("#preview-markdown")
        assert "Doomed task" in md.source

        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()

        assert "Doomed task" not in md.source
        assert "*Nothing pending.*" in md.source


@pytest.mark.asyncio
async def test_table_shortcut_expands_while_typing(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        editor = app.query_one(NoteEditor)

        for ch in "{table:2,1}":
            await pilot.press(ch)
        await pilot.pause()

        assert editor.text == "| Column 1 | Column 2 |\n| --- | --- |\n|  |  |"


@pytest.mark.asyncio
async def test_template_shortcut_expands_while_typing(config: QuillConfig) -> None:
    app = QuillApp(config)
    app.store.create("Meeting Notes", folder="Templates", body="## Attendees")
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        editor = app.query_one(NoteEditor)

        for ch in "{template:Meeting Notes}":
            await pilot.press(ch)
        await pilot.pause()

        assert editor.text == "## Attendees"


@pytest.mark.asyncio
async def test_template_shortcut_ignores_non_template_notes(config: QuillConfig) -> None:
    # {template:X} should only ever pull from the Templates folder, not any
    # arbitrary note, so a typo can't dump an unrelated note's full content.
    app = QuillApp(config)
    app.store.create("Private Journal", body="secret stuff")
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        editor = app.query_one(NoteEditor)

        for ch in "{template:Private Journal}":
            await pilot.press(ch)
        await pilot.pause()

        assert editor.text == "{template:Private Journal}"  # left untouched
        assert "secret" not in editor.text


@pytest.mark.asyncio
async def test_custom_shortcut_expands_while_typing(tmp_path: Path) -> None:
    config = QuillConfig(notes_dir=tmp_path / "notes", ai=AIConfig(enabled=False), shortcuts={"sig": "-- Me"})
    app = QuillApp(config)
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        editor = app.query_one(NoteEditor)

        for ch in "Thanks {sig}":
            await pilot.press(ch)
        await pilot.pause()

        assert editor.text == "Thanks -- Me"


@pytest.mark.asyncio
async def test_unrecognized_shortcut_left_as_typed(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("My Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        app.action_edit_note()
        await pilot.pause()
        editor = app.query_one(NoteEditor)

        for ch in "{nonexistent}":
            await pilot.press(ch)
        await pilot.pause()

        assert editor.text == "{nonexistent}"


@pytest.mark.asyncio
async def test_edit_tags_saves_and_shows_in_breadcrumb(config: QuillConfig) -> None:
    from quill.widgets.modals import EditTagsModal

    app = QuillApp(config)
    note = app.store.create("A Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()

        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, EditTagsModal)
        for ch in "work, urgent":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app.current_note.tags == ["work", "urgent"]
        assert app.store.get(note.rel_path).tags == ["work", "urgent"]
        bar = app.query_one("#breadcrumb-bar")
        assert "#work #urgent" in str(bar.render())


@pytest.mark.asyncio
async def test_edit_tags_dedupes_case_insensitively(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("A Note")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        for ch in "work, Work, WORK":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app.current_note.tags == ["work"]


@pytest.mark.asyncio
async def test_edit_tags_empty_clears_all(config: QuillConfig) -> None:
    app = QuillApp(config)
    note = app.store.create("A Note", tags=["old-tag"])

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        area = app.screen.query_one("#tags-input")
        area.value = ""
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.current_note.tags == []
        assert app.store.get(note.rel_path).tags == []


@pytest.mark.asyncio
async def test_edit_tags_cancel_leaves_tags_unchanged(config: QuillConfig) -> None:
    from quill.widgets.modals import EditTagsModal

    app = QuillApp(config)
    note = app.store.create("A Note", tags=["keep-me"])

    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_note(note.rel_path)
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, EditTagsModal)
        await pilot.press("escape")
        await pilot.pause()

        assert app.current_note.tags == ["keep-me"]


@pytest.mark.asyncio
async def test_search_by_tag(config: QuillConfig) -> None:
    from textual.widgets import RadioButton

    app = QuillApp(config)
    app.store.create("Work Note", tags=["urgent"])
    app.store.create("Other Note", tags=["someday"])

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        app.screen.query_one("#mode-tag", RadioButton).value = True
        await pilot.pause()
        for ch in "urgent":
            await pilot.press(ch)
        await pilot.pause()
        results = app.screen.query_one("#search-results")
        assert len(results.children) == 1

        await pilot.press("enter")
        await pilot.pause()
        assert app.current_note.title == "Work Note"
