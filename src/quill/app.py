"""The Quill Textual application."""

from __future__ import annotations

import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header, Static

from .ai.provider import AIProvider
from .config import QuillConfig, save_settings
from .dashboard import build_welcome_markdown
from .models import Note
from .notebooks import DEFAULT_NOTEBOOK, ensure_notebook, list_notebooks, migrate_legacy_notes
from .storage import TEMPLATES_FOLDER, NoteStore, slugify
from .widgets.ai_panel import AIPanel, NotesChanged
from .widgets.editor import NoteEditor
from .widgets.modals import (
    ConfirmModal,
    EditTagsModal,
    HelpModal,
    HistoryModal,
    InsertTemplateModal,
    LinkPickerModal,
    MoveNoteModal,
    NewFolderModal,
    NewNoteModal,
    OpenNotebookModal,
    RenameModal,
    SearchModal,
    SettingsModal,
)
from .widgets.preview import LinkActivated, NotePreview
from .widgets.sidebar import NoteChosen, NoteHighlighted, Sidebar
from .wikilinks import find_link_targets, is_url


class QuillApp(App[None]):
    TITLE = "Quill"
    # Autosave still writes to disk on every timer tick (that's the point),
    # but a toast on every single tick while actively typing is noisy -- only
    # surface one at most this often.
    AUTOSAVE_NOTIFY_MIN_GAP = 30.0

    # A reactive (rather than a plain attribute) so every place that flips
    # edit mode on/off automatically keeps footer visibility in sync (see
    # check_action) without each call site having to remember to.
    editing: reactive[bool] = reactive(False)

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
    #breadcrumb-bar {
        height: 3;
        background: $panel;
        color: $text;
        text-style: bold;
        content-align: left middle;
        padding: 0 1;
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
        Binding("f", "new_folder", "New folder"),
        Binding("e", "edit_note", "Edit"),
        Binding("ctrl+s", "save_note", "Save", show=False),
        Binding("escape", "cancel_or_close", "Cancel", show=False),
        Binding("d", "delete_note", "Delete"),
        Binding("p", "toggle_pin", "Pin"),
        Binding("m", "move_note", "Move"),
        Binding("r", "rename", "Rename"),
        Binding("h", "view_history", "History"),
        Binding("t", "edit_tags", "Tags"),
        Binding("g", "go_to_link", "Go to link"),
        Binding("slash", "search", "Search"),
        Binding("ctrl+t", "toggle_checkbox", "Toggle checkbox", show=False),
        Binding("ctrl+g", "insert_template", "Insert template"),  # shown only while editing; see check_action
        Binding("a", "toggle_ai", "AI"),
        Binding("o", "open_notebook", "Open notebook"),
        # 'ctrl+o' is a silent alias reachable even mid-edit (a plain letter
        # is swallowed as text by the editor, same reason template-insert
        # uses ctrl+g) -- needed here specifically so the unsaved-changes
        # prompt is reachable from an active edit, not just from browsing.
        Binding("ctrl+o", "open_notebook", "Open notebook", show=False),
        Binding("s", "settings", "Settings"),
        Binding("question_mark", "help", "Help"),
        Binding("b", "focus_sidebar", "Sidebar"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: QuillConfig) -> None:
        super().__init__()
        self.config = config
        # Defensive: load_config() already does this for the normal CLI
        # entry point, but the App can also be constructed directly (tests,
        # embedding) without going through it.
        migrate_legacy_notes(config.notes_dir)
        self.notebook = config.current_notebook or DEFAULT_NOTEBOOK
        notebook_dir = ensure_notebook(config.notes_dir, self.notebook)
        self.store = NoteStore(notebook_dir, history_enabled=config.history_enabled, max_revisions=config.max_revisions)
        self.ai_provider = AIProvider(self.store, config.ai)
        self.current_note: Note | None = None
        self._autosave_timer: Timer | None = None
        self._last_autosave_notify = 0.0
        self._welcome_markdown: str | None = None
        self.title = f"Quill: {self.notebook}"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield Sidebar()
            with Vertical(id="content"):
                yield Static("", id="breadcrumb-bar")
                yield NotePreview(id="note-preview")
                yield NoteEditor()
            yield AIPanel(self.ai_provider)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(NoteEditor).display = False
        self.store.create_folder(TEMPLATES_FOLDER)
        self.refresh_sidebar()
        self._show_preview(None)  # dashboard: pending tasks, stale notes
        self._restart_autosave_timer()
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "toggle_ai":
            # Hides (and disables) the "AI" footer shortcut entirely when the
            # assistant is turned off in settings, rather than leaving a dead
            # entry that just explains it's unavailable.
            return self.config.ai.enabled
        if action == "insert_template":
            # Only meaningful while editing (it inserts at the cursor) --
            # shown in the footer only then, rather than always-hidden.
            return self.editing
        return True

    def watch_editing(self, editing: bool) -> None:
        self.refresh_bindings()

    def _restart_autosave_timer(self) -> None:
        if self._autosave_timer is not None:
            self._autosave_timer.stop()
        self._autosave_timer = self.set_interval(self.config.autosave_interval, self._autosave_tick)

    def _autosave_tick(self) -> None:
        if self.config.save_mode != "autosave" or not self.has_unsaved_changes:
            return
        self._persist_current_note()
        now = time.monotonic()
        if now - self._last_autosave_notify >= self.AUTOSAVE_NOTIFY_MIN_GAP:
            self._last_autosave_notify = now
            self.notify("Autosaved", timeout=1.0, severity="information")

    @property
    def has_unsaved_changes(self) -> bool:
        if not self.editing or self.current_note is None:
            return False
        return self.query_one(NoteEditor).text != self.current_note.body

    async def action_quit(self) -> None:
        if self.has_unsaved_changes:
            def handle(confirmed: bool | None) -> None:
                if confirmed:
                    self.exit()

            self.push_screen(
                ConfirmModal(
                    f"'{self.current_note.title}' has unsaved changes. Quit without saving?",
                    confirm_label="Quit without saving",
                ),
                handle,
            )
            return
        self.exit()

    def refresh_sidebar(self, select: str | None = None) -> None:
        notes = self.store.list_notes()
        select = select if select is not None else (self.current_note.rel_path if self.current_note else None)
        self.query_one(Sidebar).refresh_notes(notes, selected_rel=select, folders=self.store.list_folders())
        editor = self.query_one(NoteEditor)
        editor.set_known_titles([n.title for n in notes])
        editor.configure_shortcuts(self.config.shortcuts, self._resolve_template_body)

    def _resolve_template_body(self, name: str) -> str | None:
        """Look up a template by name for '{template:Name}' expansion --
        restricted to notes actually inside the Templates folder, not just
        any note, so a typo can't dump an unrelated note's full content."""
        if not name:
            return None
        note = self.store.resolve_link(name)
        if note is None:
            return None
        if note.folder != TEMPLATES_FOLDER and not note.folder.startswith(f"{TEMPLATES_FOLDER}/"):
            return None
        return note.body

    def _show_preview(self, note: Note | None) -> None:
        welcome = build_welcome_markdown(self.store) if note is None else None
        self._welcome_markdown = welcome
        self.query_one(NotePreview).show_note(note, resolve_link=self._note_exists, welcome_markdown=welcome)
        self.query_one("#breadcrumb-bar", Static).update(self._breadcrumb_text(note) if note else "")

    def _breadcrumb_text(self, note: Note) -> str:
        # Shows where the note lives, not just its title, so notes that
        # share a title in different folders are easy to tell apart.
        path = f"{note.folder.replace('/', ' › ')} › {note.title}" if note.folder else note.title
        if note.tags:
            path += "   " + " ".join(f"#{t}" for t in note.tags)
        return path

    def _note_exists(self, target: str) -> bool:
        return self.store.resolve_link(target) is not None

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
        self._show_preview(note)

    # -- sidebar events ---------------------------------------------------

    def on_note_highlighted(self, event: NoteHighlighted) -> None:
        # Deliberately ignore event.rel_path and re-read the sidebar's
        # current cursor instead: rebuilding the tree (e.g. via
        # refresh_sidebar) posts its own NodeHighlighted as a side effect,
        # asynchronously, which can otherwise arrive *after* a programmatic
        # move_cursor() and reentrantly re-open a stale note -- clobbering
        # whatever was just explicitly opened (e.g. via a wiki-link jump).
        # Reading the live cursor is self-correcting regardless of when a
        # (possibly stale) message actually gets processed.
        if self.editing:
            return
        rel_path = Sidebar.note_rel_path_for(self.query_one(Sidebar).cursor_node)
        if rel_path:
            self.open_note(rel_path)

    def on_note_chosen(self, event: NoteChosen) -> None:
        rel_path = Sidebar.note_rel_path_for(self.query_one(Sidebar).cursor_node)
        if rel_path:
            self.open_note(rel_path)

    # -- preview link events -------------------------------------------

    def on_link_activated(self, event: LinkActivated) -> None:
        self._go_to_link_target(event.target)

    def _go_to_link_target(self, target: str) -> None:
        if is_url(target):
            import webbrowser

            webbrowser.open(target)
            return
        note = self.store.resolve_link(target)
        if note is None:
            self.notify(f"No note titled '{target}' yet. Press 'n' to create it.", severity="warning")
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
        # Defaults to wherever the sidebar is currently pointed -- a folder
        # header if one is highlighted, otherwise the open note's folder.
        default_folder = self.query_one(Sidebar).current_folder()

        def handle(result: tuple[str, str] | None) -> None:
            if result is None:
                return
            title, folder = result
            note = self.store.create(title=title, folder=folder)
            self.refresh_sidebar(select=note.rel_path)
            self.open_note(note.rel_path)
            self.action_edit_note()

        self.push_screen(NewNoteModal(default_folder, known_folders=self.store.list_folders()), handle)

    def action_new_folder(self) -> None:
        # One level under wherever the sidebar is currently pointed.
        parent_folder = self.query_one(Sidebar).current_folder()

        def handle(name: str | None) -> None:
            if not name:
                return
            slug = slugify(name)
            new_folder = f"{parent_folder}/{slug}" if parent_folder else slug
            self.store.create_folder(new_folder)
            self.refresh_sidebar()
            self.notify(f"Created folder '{new_folder}'.")

        self.push_screen(NewFolderModal(parent_folder), handle)

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

    def _persist_current_note(self) -> None:
        """Write the editor's current text to disk, without leaving edit mode.
        Used by both manual save and autosave."""
        if self.current_note is None:
            return
        editor = self.query_one(NoteEditor)
        self.current_note.body = editor.text
        self.store.save(self.current_note)
        self.refresh_sidebar(select=self.current_note.rel_path)

    def action_save_note(self) -> None:
        if not self.editing or self.current_note is None:
            return
        self._persist_current_note()
        self.editing = False
        editor = self.query_one(NoteEditor)
        editor.display = False
        self.query_one(NotePreview).display = True
        self._show_preview(self.current_note)
        self.notify("Saved.")

    def action_cancel_or_close(self) -> None:
        if self.editing:
            if self.has_unsaved_changes:
                def handle(confirmed: bool | None) -> None:
                    if confirmed:
                        self._discard_edit()

                self.push_screen(
                    ConfirmModal("Discard unsaved changes?", confirm_label="Discard"),
                    handle,
                )
            else:
                self._discard_edit()
            return
        ai_panel = self.query_one(AIPanel)
        if ai_panel.has_class("-visible"):
            ai_panel.toggle()
        # Nothing else to back out of -- fall back to a safe, known state
        # rather than leaving focus wherever it happened to end up.
        self.query_one(Sidebar).focus()

    def _discard_edit(self) -> None:
        self.editing = False
        self.query_one(NoteEditor).display = False
        self.query_one(NotePreview).display = True
        if self.current_note:
            self._show_preview(self.current_note)

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
            self._show_preview(None)
            self.refresh_sidebar(select=None)
            self.notify(f"Deleted '{note.title}'.")

        self.push_screen(ConfirmModal(f"Delete '{note.title}'? This can't be undone."), handle)

    def action_toggle_pin(self) -> None:
        if self.current_note is None:
            return
        note = self.store.toggle_pin(self.current_note.rel_path)
        self.current_note = note
        self.refresh_sidebar(select=note.rel_path)
        self._show_preview(note)

    def action_edit_tags(self) -> None:
        if self.current_note is None:
            self.notify("No note selected.", severity="warning")
            return
        note = self.current_note

        def handle(tags: list[str] | None) -> None:
            if tags is None:
                return
            note.tags = tags
            self.store.save(note, touch=False)
            self.current_note = note
            self._show_preview(note)
            self.refresh_sidebar(select=note.rel_path)

        self.push_screen(EditTagsModal(note.title, note.tags), handle)

    def action_view_history(self) -> None:
        if self.current_note is None:
            self.notify("No note selected.", severity="warning")
            return
        note = self.current_note
        revisions = self.store.list_revisions(note.rel_path)
        if not revisions:
            self.notify("No revision history for this note yet.", severity="warning")
            return

        def handle(revision) -> None:
            if revision is None:
                return
            restored = self.store.restore_revision(note, revision)
            self.current_note = restored
            self._show_preview(restored)
            self.refresh_sidebar(select=restored.rel_path)
            self.notify(f"Restored the version from {revision.timestamp:%Y-%m-%d %H:%M:%S}.")

        self.push_screen(HistoryModal(note.title, revisions), handle)

    def action_move_note(self) -> None:
        if self.current_note is None:
            self.notify("No note selected.", severity="warning")
            return
        note = self.current_note

        def handle(new_folder: str | None) -> None:
            if new_folder is None:
                return
            moved = self.store.move(note, new_folder)
            self.current_note = moved
            self.refresh_sidebar(select=moved.rel_path)
            self._show_preview(moved)
            self.notify(f"Moved to '{new_folder or '(top level)'}'.")

        self.push_screen(MoveNoteModal(note.title, note.folder, self.store.list_folders()), handle)

    def action_rename(self) -> None:
        sidebar = self.query_one(Sidebar)
        folder = Sidebar.folder_for(sidebar.cursor_node)
        if folder:
            self._rename_folder(folder)
            return
        if self.current_note is not None:
            self._rename_note(self.current_note)
            return
        self.notify("Nothing to rename.", severity="warning")

    def _rename_note(self, note: Note) -> None:
        def handle(new_title: str | None) -> None:
            if not new_title or new_title == note.title:
                return
            renamed = self.store.rename(note, new_title)
            self.current_note = renamed
            self.refresh_sidebar(select=renamed.rel_path)
            self._show_preview(renamed)
            self.notify(f"Renamed to '{new_title}'.")

        self.push_screen(RenameModal("Rename note", note.title), handle)

    def _rename_folder(self, folder: str) -> None:
        current_name = folder.split("/")[-1]

        def handle(new_name: str | None) -> None:
            if not new_name:
                return
            try:
                new_folder = self.store.rename_folder(folder, new_name)
            except (ValueError, FileNotFoundError, FileExistsError) as exc:
                self.notify(f"Couldn't rename folder: {exc}", severity="error")
                return
            # If the open note was inside the renamed folder (or a
            # subfolder of it), its rel_path changed too -- reload it fresh.
            if self.current_note is not None and self.current_note.rel_path.startswith(f"{folder}/"):
                new_rel = new_folder + self.current_note.rel_path[len(folder):]
                self.current_note = None
                self.open_note(new_rel)
            self.refresh_sidebar()
            self.notify(f"Renamed folder to '{new_folder}'.")

        self.push_screen(RenameModal("Rename folder", current_name), handle)

    def action_search(self) -> None:
        if self.editing:
            return

        def handle(rel_path: str | None) -> None:
            if rel_path:
                self.open_note(rel_path)
                self.refresh_sidebar(select=rel_path)

        self.push_screen(SearchModal(self.store.list_notes()), handle)

    def action_go_to_link(self) -> None:
        if self.editing:
            return
        if self.current_note is not None:
            body = self.current_note.body
        elif self._welcome_markdown is not None:
            # Viewing the dashboard (pending tasks / stale notes) rather
            # than a real note -- its links work the same way.
            body = self._welcome_markdown
        else:
            return
        links = find_link_targets(body)
        if not links:
            self.notify("No [[links]] to follow here.", severity="warning")
            return
        if len(links) == 1:
            target, _ = links[0]
            self._go_to_link_target(target)
            return

        def handle(target: str | None) -> None:
            if target:
                self._go_to_link_target(target)

        self.push_screen(LinkPickerModal(links), handle)

    def action_toggle_checkbox(self) -> None:
        if self.editing:
            self.query_one(NoteEditor).toggle_checkbox_on_current_line()

    def action_insert_template(self) -> None:
        if not self.editing:
            self.notify("Start editing a note first (press 'e').", severity="warning")
            return
        templates = self.store.list_templates()
        if not templates:
            self.notify(
                f"No templates yet -- create notes inside the '{TEMPLATES_FOLDER}' folder to use them here.",
                severity="warning",
            )
            return

        def handle(rel_path: str | None) -> None:
            if not rel_path:
                return
            try:
                template = self.store.get(rel_path)
            except Exception:
                self.notify("That template is gone now.", severity="error")
                return
            self.query_one(NoteEditor).insert_at_cursor(template.body)

        self.push_screen(InsertTemplateModal(templates), handle)

    def action_focus_sidebar(self) -> None:
        self.query_one(Sidebar).focus()

    def action_help(self) -> None:
        self.push_screen(HelpModal(self.config.shortcuts))

    def action_toggle_ai(self) -> None:
        panel = self.query_one(AIPanel)
        panel.toggle()
        if not panel.has_class("-visible"):
            self.query_one(Sidebar).focus()

    def action_settings(self) -> None:
        def handle(new_config: QuillConfig | None) -> None:
            if new_config is None:
                return
            new_config.current_notebook = self.notebook  # not editable from Settings; open_notebook ('o') owns this
            save_settings(new_config)
            dir_changed = new_config.notes_dir != self.config.notes_dir
            self.config = new_config
            if dir_changed:
                migrate_legacy_notes(new_config.notes_dir)
                notebook_dir = ensure_notebook(new_config.notes_dir, self.notebook)
                self.store = NoteStore(
                    notebook_dir,
                    history_enabled=new_config.history_enabled,
                    max_revisions=new_config.max_revisions,
                )
                self.store.create_folder(TEMPLATES_FOLDER)
                self.current_note = None
                self.editing = False
                self.query_one(NoteEditor).display = False
                self.query_one(NotePreview).display = True
                self._show_preview(None)
            else:
                self.store.history_enabled = new_config.history_enabled
                self.store.max_revisions = new_config.max_revisions
            self.ai_provider.reconfigure(self.store, new_config.ai)
            self.refresh_sidebar()
            self._restart_autosave_timer()
            self.refresh_bindings()
            self.notify("Settings saved.")

        self.push_screen(SettingsModal(self.config), handle)

    def action_open_notebook(self) -> None:
        def proceed() -> None:
            notebooks = list_notebooks(self.config.notes_dir)
            self.push_screen(OpenNotebookModal(notebooks, self.notebook), handle)

        def handle(name: str | None) -> None:
            if not name or name == self.notebook:
                return
            self._switch_notebook(name)

        if self.has_unsaved_changes:
            def confirm_handle(confirmed: bool | None) -> None:
                if confirmed:
                    proceed()

            self.push_screen(
                ConfirmModal(
                    f"'{self.current_note.title}' has unsaved changes. Switch notebooks without saving?",
                    confirm_label="Switch without saving",
                ),
                confirm_handle,
            )
            return
        proceed()

    def _switch_notebook(self, name: str) -> None:
        notebook_dir = ensure_notebook(self.config.notes_dir, name)
        self.notebook = name
        self.config.current_notebook = name
        save_settings(self.config)

        self.store = NoteStore(
            notebook_dir, history_enabled=self.config.history_enabled, max_revisions=self.config.max_revisions
        )
        self.store.create_folder(TEMPLATES_FOLDER)
        self.ai_provider.reconfigure(self.store, self.config.ai)

        self.current_note = None
        self.editing = False
        self.query_one(NoteEditor).display = False
        self.query_one(NotePreview).display = True
        self._show_preview(None)
        self.refresh_sidebar()
        self.title = f"Quill: {name}"
        self.notify(f"Switched to notebook '{name}'.")


def run_app(config: QuillConfig) -> None:
    QuillApp(config).run()
