"""A text input with substring-narrowed autocomplete against known folders."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from ..wikilinks import suggest_titles


class FolderInput(Vertical):
    """Reuses the same substring-narrowing used for wiki-link autocomplete
    (e.g. "test n" -> "test note 1") to suggest existing folder paths."""

    def __init__(self, value: str = "", placeholder: str = "Folder (optional)", input_id: str = "folder-input") -> None:
        super().__init__()
        self._initial_value = value
        self._placeholder = placeholder
        self._input_id = input_id
        self._folders: list[str] = []

    def compose(self) -> ComposeResult:
        yield Input(value=self._initial_value, placeholder=self._placeholder, id=self._input_id)
        yield OptionList(id=f"{self._input_id}-suggestions")

    def on_mount(self) -> None:
        self.query_one(OptionList).display = False

    def set_known_folders(self, folders: list[str]) -> None:
        self._folders = folders

    @property
    def value(self) -> str:
        return self.query_one(Input).value.strip()

    def focus_input(self) -> None:
        self.query_one(Input).focus()

    def _suggestions(self) -> OptionList:
        return self.query_one(f"#{self._input_id}-suggestions", OptionList)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != self._input_id:
            return
        suggestions = self._suggestions()
        partial = event.value.strip()
        if not partial:
            suggestions.display = False
            return
        matches = [f for f in suggest_titles(partial, self._folders) if f.lower() != partial.lower()]
        suggestions.clear_options()
        if not matches:
            suggestions.display = False
            return
        suggestions.add_options([Option(folder, id=folder) for folder in matches])
        suggestions.highlighted = 0
        suggestions.display = True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != self._input_id:
            return
        suggestions = self._suggestions()
        if suggestions.display and suggestions.highlighted is not None:
            # A suggestion is open: Enter accepts it instead of submitting
            # the enclosing form (matches the wiki-link editor's behavior).
            option = suggestions.get_option_at_index(suggestions.highlighted)
            self.query_one(Input).value = str(option.id)
            suggestions.display = False
            event.stop()

    def on_key(self, event) -> None:
        suggestions = self._suggestions()
        if not suggestions.display:
            return
        if event.key == "escape":
            event.stop()
            event.prevent_default()
            suggestions.display = False
        elif event.key == "down":
            event.stop()
            event.prevent_default()
            suggestions.action_cursor_down()
        elif event.key == "up":
            event.stop()
            event.prevent_default()
            suggestions.action_cursor_up()
