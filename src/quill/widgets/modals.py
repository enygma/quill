"""Modal dialogs: confirm delete, new note, and search."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, RadioButton, RadioSet, Static, Switch

from ..config import AIConfig, QuillConfig
from ..models import Note
from ..search import SearchResult, date_search, fuzzy_search, parse_date_query, text_search

HELP_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Notes",
        [
            ("n", "New note"),
            ("e", "Edit selected note"),
            ("ctrl+s", "Save now (works in both autosave and manual mode)"),
            ("escape", "Cancel edit, or close the AI panel / a dialog"),
            ("d", "Delete selected note (asks to confirm)"),
            ("p", "Pin / unpin selected note"),
        ],
    ),
    (
        "Editing",
        [
            ("ctrl+t", "Toggle checkbox ('- [ ]') on the current line"),
            ("[[", "Start a wiki-link; autocomplete suggests matching titles"),
            ("tab / enter", "Accept the highlighted wiki-link suggestion"),
        ],
    ),
    (
        "Navigation & search",
        [
            ("up / down", "Move through the sidebar or a results list"),
            ("enter", "Open the highlighted note, or a clicked [[wiki link]]"),
            ("/", "Search notes (text, fuzzy, or date)"),
        ],
    ),
    (
        "App",
        [
            ("a", "Toggle the AI assistant panel"),
            ("s", "Settings (notes directory, AI connection)"),
            ("?", "Show this help"),
            ("q", "Quit"),
        ],
    ),
]


class ConfirmModal(ModalScreen[bool]):
    """A yes/no confirmation dialog."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    #confirm-box {
        width: 60;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    #confirm-buttons {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    #confirm-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, message: str, confirm_label: str = "Delete") -> None:
        super().__init__()
        self._message = message
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self._message)
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button(self._confirm_label, id="confirm", variant="error")

    @on(Button.Pressed, "#confirm")
    def _confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(False)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)


class NewNoteModal(ModalScreen[tuple[str, str] | None]):
    """Prompts for a new note's title and (optional) folder."""

    DEFAULT_CSS = """
    NewNoteModal {
        align: center middle;
    }
    #new-note-box {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #new-note-box Input {
        margin-top: 1;
    }
    #new-note-buttons {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    #new-note-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, default_folder: str = "") -> None:
        super().__init__()
        self._default_folder = default_folder

    def compose(self) -> ComposeResult:
        with Vertical(id="new-note-box"):
            yield Label("New note")
            yield Input(placeholder="Title", id="title-input")
            yield Input(placeholder="Folder (optional)", value=self._default_folder, id="folder-input")
            with Horizontal(id="new-note-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Create", id="create", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#title-input", Input).focus()

    @on(Input.Submitted)
    def _submitted(self) -> None:
        self._create()

    @on(Button.Pressed, "#create")
    def _create_pressed(self) -> None:
        self._create()

    def _create(self) -> None:
        title = self.query_one("#title-input", Input).value.strip()
        folder = self.query_one("#folder-input", Input).value.strip()
        if not title:
            return
        self.dismiss((title, folder))

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class SettingsModal(ModalScreen[QuillConfig | None]):
    """Edit global Quill settings (notes directory, AI connection) -> ~/.quillrc."""

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }
    #settings-box {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #settings-box Input {
        margin-top: 1;
    }
    .settings-label {
        margin-top: 1;
        color: $text-muted;
    }
    #ai-enabled-row {
        height: auto;
        margin-top: 1;
    }
    #ai-enabled-row Label {
        margin-left: 1;
        margin-top: 1;
    }
    #settings-hint {
        color: $text-muted;
        margin-top: 1;
    }
    #settings-buttons {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    #settings-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, config: QuillConfig) -> None:
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-box"):
            yield Label("Settings  (saved to ~/.quillrc)")
            yield Label("Notes directory", classes="settings-label")
            yield Input(value=str(self._config.notes_dir), id="notes-dir-input")
            yield Label("Saving", classes="settings-label")
            with RadioSet(id="save-mode"):
                yield RadioButton("Autosave", value=self._config.save_mode == "autosave", id="save-mode-autosave")
                yield RadioButton(
                    "Manual (ctrl+s only)", value=self._config.save_mode == "manual", id="save-mode-manual"
                )
            yield Label("Autosave interval (seconds)", classes="settings-label")
            yield Input(value=str(self._config.autosave_interval), id="autosave-interval-input")
            yield Label("AI provider", classes="settings-label")
            yield Input(value=self._config.ai.provider, id="ai-provider-input")
            yield Label("AI model", classes="settings-label")
            yield Input(value=self._config.ai.model, id="ai-model-input")
            yield Label("API key env var (read from environment)", classes="settings-label")
            yield Input(value=self._config.ai.api_key_env, id="ai-key-env-input")
            yield Label("API key (optional; stored in plain text in ~/.quillrc if set)", classes="settings-label")
            yield Input(value=self._config.ai.api_key or "", password=True, id="ai-key-input")
            with Horizontal(id="ai-enabled-row"):
                yield Switch(value=self._config.ai.enabled, id="ai-enabled-switch")
                yield Label("AI assistant enabled")
            yield Static("Changing the notes directory takes effect immediately.", id="settings-hint")
            with Horizontal(id="settings-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="save", variant="primary")

    @on(Button.Pressed, "#save")
    def _save(self) -> None:
        notes_dir = self.query_one("#notes-dir-input", Input).value.strip()
        ai = AIConfig(
            provider=self.query_one("#ai-provider-input", Input).value.strip() or "anthropic",
            model=self.query_one("#ai-model-input", Input).value.strip() or "claude-sonnet-5",
            api_key_env=self.query_one("#ai-key-env-input", Input).value.strip() or "ANTHROPIC_API_KEY",
            api_key=self.query_one("#ai-key-input", Input).value.strip() or None,
            enabled=self.query_one("#ai-enabled-switch", Switch).value,
        )

        save_mode_pressed = self.query_one("#save-mode", RadioSet).pressed_button
        save_mode = "manual" if save_mode_pressed and save_mode_pressed.id == "save-mode-manual" else "autosave"

        try:
            autosave_interval = max(1.0, float(self.query_one("#autosave-interval-input", Input).value.strip()))
        except ValueError:
            autosave_interval = self._config.autosave_interval

        from pathlib import Path

        new_config = QuillConfig(
            notes_dir=Path(notes_dir).expanduser().resolve(),
            ai=ai,
            save_mode=save_mode,
            autosave_interval=autosave_interval,
        )
        self.dismiss(new_config)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class SearchModal(ModalScreen[str | None]):
    """Search notes by text, fuzzy match, or date. Returns a chosen rel_path."""

    DEFAULT_CSS = """
    SearchModal {
        align: center middle;
    }
    #search-box {
        width: 80;
        height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #search-mode {
        height: auto;
        margin-top: 1;
    }
    #search-results {
        height: 1fr;
        margin-top: 1;
        border: solid $panel;
    }
    #search-hint {
        color: $text-muted;
    }
    """

    def __init__(self, notes: list[Note]) -> None:
        super().__init__()
        self._notes = notes

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label("Search notes")
            yield Input(placeholder="Type to search...", id="search-input")
            with RadioSet(id="search-mode"):
                yield RadioButton("Text", value=True, id="mode-text")
                yield RadioButton("Fuzzy", id="mode-fuzzy")
                yield RadioButton("Date (YYYY-MM-DD or 'since:YYYY-MM-DD until:YYYY-MM-DD')", id="mode-date")
            yield Static("Enter opens the top result, Esc closes", id="search-hint")
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def _current_mode(self) -> str:
        radio = self.query_one("#search-mode", RadioSet)
        pressed = radio.pressed_button
        if pressed is None:
            return "text"
        return str(pressed.id).replace("mode-", "")

    @on(Input.Changed, "#search-input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        self._run_search(event.value)

    @on(Input.Submitted, "#search-input")
    def _on_input_submitted(self) -> None:
        # Enter from the search box opens the top result directly, so users
        # don't have to Tab into the results list first.
        results_view = self.query_one("#search-results", ListView)
        if results_view.children:
            first_item = results_view.children[0]
            rel_path = getattr(first_item, "data_rel_path", None)
            if rel_path:
                self.dismiss(rel_path)

    @on(RadioSet.Changed)
    def _on_mode_changed(self) -> None:
        self._run_search(self.query_one("#search-input", Input).value)

    def _run_search(self, query: str) -> None:
        mode = self._current_mode()
        results: list[SearchResult] = []
        if not query.strip():
            results = []
        elif mode == "text":
            results = text_search(self._notes, query)
        elif mode == "fuzzy":
            results = fuzzy_search(self._notes, query)
        elif mode == "date":
            results = self._date_search(query)

        results_view = self.query_one("#search-results", ListView)
        results_view.clear()
        for result in results[:50]:
            pin = "📌 " if result.note.pinned else ""
            label = f"{pin}{result.note.title}  [dim]({result.note.rel_path})[/dim]"
            if result.snippet:
                label += f"\n   [dim]{result.snippet}[/dim]"
            item = ListItem(Label(label))
            item.data_rel_path = result.note.rel_path  # type: ignore[attr-defined]
            results_view.append(item)

    def _date_search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if query.startswith("since:") or "until:" in query or "since:" in query:
            since = until = None
            for part in query.split():
                if part.startswith("since:"):
                    since = parse_date_query(part[len("since:"):])
                elif part.startswith("until:"):
                    until = parse_date_query(part[len("until:"):])
            return date_search(self._notes, since=since, until=until)
        dt = parse_date_query(query)
        if dt is None:
            return []
        return date_search(self._notes, on=dt)

    @on(ListView.Selected, "#search-results")
    def _on_selected(self, event: ListView.Selected) -> None:
        rel_path = getattr(event.item, "data_rel_path", None)
        if rel_path:
            self.dismiss(rel_path)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class HelpModal(ModalScreen[None]):
    """Lists every keybinding, grouped by category."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    #help-box {
        width: 64;
        height: auto;
        max-height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #help-box .help-section {
        margin-bottom: 1;
    }
    #help-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "dismiss_help", "Close"), ("question_mark", "dismiss_help", "Close")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-box"):
            yield Label("Keyboard shortcuts")
            for section_title, rows in HELP_SECTIONS:
                key_width = max(len(key) for key, _ in rows)
                lines = "\n".join(f"  [b]{key.ljust(key_width)}[/b]  {desc}" for key, desc in rows)
                yield Static(f"[u]{section_title}[/u]\n{lines}", classes="help-section")
            yield Static("Press Esc or ? to close", id="help-hint")

    def action_dismiss_help(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key in ("escape", "question_mark"):
            self.dismiss(None)
