"""The Quill Textual application."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from .ai.provider import AIProvider
from .config import QuillConfig, save_settings
from .models import Note
from .storage import NoteStore
from .widgets.ai_panel import AIPanel, NotesChanged
from .widgets.editor import NoteEditor
from .widgets.modals import ConfirmModal, NewNoteModal, SearchModal, SettingsModal
from .widgets.preview import NotePreview, WikiLinkActivated
from .widgets.sidebar import NoteChosen, NoteHighlighted, Sidebar


class QuillApp(App[None]):
    TITLE = "Quill"
    CSS = """
    #body {
        height: 1fr;
    }
    Sidebar {
        width: 34;
        border-right: solid $panel;
    }
    #content {
        width: 1fr;
    }
    NoteEditor, NotePreview {
        height: 1fr;
    }
    #link-suggestions {
        height: auto;
        max-height: 8;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("n", "new_note", "New"),
        Binding("e", "edit_note", "Edit"),
        Binding("ctrl+s", "save_note", "Save", show=False),
        Binding("escape", "cancel_or_close", "Cancel", show=False),
        Binding("d", "delete_note", "Delete"),
        Binding("p", "toggle_pin", "Pin"),
        Binding("slash", "search", "Search"),
        Binding("ctrl+t", "toggle_checkbox", "Toggle checkbox", show=False),
        Binding("a", "toggle_ai", "AI"),
        Binding("s", "settings", "Settings"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: QuillConfig) -> None:
        super().__init__()
        self.config = config
        self.store = NoteStore(config.notes_dir)
        self.ai_provider = AIProvider(self.store, config.ai)
        self.current_note: Note | None = None
        self.editing = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield Sidebar()
            with Horizontal(id="content"):
                yield NotePreview(id="note-preview")
                yield NoteEditor()
            yield AIPanel(self.ai_provider)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(NoteEditor).display = False
        self.refresh_sidebar()

    def refresh_sidebar(self, select: str | None = None) -> None:
        notes = self.store.list_notes()
        select = select if select is not None else (self.current_note.rel_path if self.current_note else None)
        self.query_one(Sidebar).refresh_notes(notes, selected_rel=select)
        self.query_one(NoteEditor).set_known_titles([n.title for n in notes])

    def open_note(self, rel_path: str) -> None:
        try:
            note = self.store.get(rel_path)
        except Exception:
            self.notify(f"Couldn't open note: {rel_path}", severity="error")
            return
        self.current_note = note
        self.editing = False
        self.query_one(NoteEditor).display = False
        self.query_one(NotePreview).display = True
        self.query_one(NotePreview).show_note(note)
        self.sub_title = note.rel_path

    # -- sidebar events ---------------------------------------------------

    def on_note_highlighted(self, event: NoteHighlighted) -> None:
        if not self.editing:
            self.open_note(event.rel_path)

    def on_note_chosen(self, event: NoteChosen) -> None:
        self.open_note(event.rel_path)

    # -- preview wiki-link events -------------------------------------------

    def on_wiki_link_activated(self, event: WikiLinkActivated) -> None:
        note = self.store.resolve_link(event.target)
        if note is None:
            self.notify(f"No note titled '{event.target}' yet. Press 'n' to create it.", severity="warning")
            return
        self.open_note(note.rel_path)
        self.refresh_sidebar(select=note.rel_path)

    # -- AI panel events ----------------------------------------------------

    def on_notes_changed(self, event: NotesChanged) -> None:
        self.refresh_sidebar()
        if self.current_note is not None:
            self.open_note(self.current_note.rel_path)

    # -- actions ------------------------------------------------------------

    def action_new_note(self) -> None:
        default_folder = self.current_note.folder if self.current_note else ""

        def handle(result: tuple[str, str] | None) -> None:
            if result is None:
                return
            title, folder = result
            note = self.store.create(title=title, folder=folder)
            self.refresh_sidebar(select=note.rel_path)
            self.open_note(note.rel_path)
            self.action_edit_note()

        self.push_screen(NewNoteModal(default_folder), handle)

    def action_edit_note(self) -> None:
        if self.current_note is None:
            self.notify("No note selected.", severity="warning")
            return
        self.editing = True
        editor = self.query_one(NoteEditor)
        editor.load_text(self.current_note.body)
        self.query_one(NotePreview).display = False
        editor.display = True
        editor.focus_editor()

    def action_save_note(self) -> None:
        if not self.editing or self.current_note is None:
            return
        editor = self.query_one(NoteEditor)
        self.current_note.body = editor.text
        self.store.save(self.current_note)
        self.editing = False
        editor.display = False
        self.query_one(NotePreview).display = True
        self.query_one(NotePreview).show_note(self.current_note)
        self.refresh_sidebar(select=self.current_note.rel_path)
        self.notify("Saved.")

    def action_cancel_or_close(self) -> None:
        if self.editing:
            self.editing = False
            self.query_one(NoteEditor).display = False
            self.query_one(NotePreview).display = True
            if self.current_note:
                self.query_one(NotePreview).show_note(self.current_note)
            return
        ai_panel = self.query_one(AIPanel)
        if ai_panel.has_class("-visible"):
            ai_panel.toggle()
            self.query_one(Sidebar).focus()

    def action_delete_note(self) -> None:
        if self.current_note is None:
            self.notify("No note selected.", severity="warning")
            return
        note = self.current_note

        def handle(confirmed: bool | None) -> None:
            if not confirmed:
                return
            self.store.delete(note.rel_path)
            self.current_note = None
            self.query_one(NotePreview).show_note(None)
            self.sub_title = ""
            self.refresh_sidebar(select=None)
            self.notify(f"Deleted '{note.title}'.")

        self.push_screen(ConfirmModal(f"Delete '{note.title}'? This can't be undone."), handle)

    def action_toggle_pin(self) -> None:
        if self.current_note is None:
            return
        note = self.store.toggle_pin(self.current_note.rel_path)
        self.current_note = note
        self.refresh_sidebar(select=note.rel_path)
        self.query_one(NotePreview).show_note(note)

    def action_search(self) -> None:
        if self.editing:
            return

        def handle(rel_path: str | None) -> None:
            if rel_path:
                self.open_note(rel_path)
                self.refresh_sidebar(select=rel_path)

        self.push_screen(SearchModal(self.store.list_notes()), handle)

    def action_toggle_checkbox(self) -> None:
        if self.editing:
            self.query_one(NoteEditor).toggle_checkbox_on_current_line()

    def action_toggle_ai(self) -> None:
        panel = self.query_one(AIPanel)
        panel.toggle()
        if not panel.has_class("-visible"):
            self.query_one(Sidebar).focus()

    def action_settings(self) -> None:
        def handle(new_config: QuillConfig | None) -> None:
            if new_config is None:
                return
            save_settings(new_config)
            dir_changed = new_config.notes_dir != self.config.notes_dir
            self.config = new_config
            if dir_changed:
                self.store = NoteStore(new_config.notes_dir)
                self.current_note = None
                self.editing = False
                self.query_one(NoteEditor).display = False
                self.query_one(NotePreview).display = True
                self.query_one(NotePreview).show_note(None)
                self.sub_title = ""
            self.ai_provider.reconfigure(self.store, new_config.ai)
            self.refresh_sidebar()
            self.notify("Settings saved.")

        self.push_screen(SettingsModal(self.config), handle)


def run_app(config: QuillConfig) -> None:
    QuillApp(config).run()
