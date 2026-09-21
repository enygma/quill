"""Editable Markdown text area with live [[wiki-link]] autocomplete."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList, TextArea
from textual.widgets.option_list import Option

from ..wikilinks import find_open_link, suggest_titles

CHECKBOX_UNCHECKED = "- [ ]"
CHECKBOX_CHECKED = "- [x]"


class WikiLinkTextArea(TextArea):
    """A TextArea that lets the wiki-link suggestion popup claim Enter.

    TextArea's own `_on_key` treats Enter as "insert a newline" and stops
    the event right there, before it would otherwise bubble up to
    NoteEditor.on_key. That's fine normally, but while the suggestion
    popup is open, Enter should accept the highlighted suggestion instead
    -- so that case has to be intercepted here, ahead of TextArea's own
    handling, rather than relying on bubbling.
    """

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            editor = self.parent
            if isinstance(editor, NoteEditor) and editor.suggestions_visible:
                event.stop()
                event.prevent_default()
                editor.accept_highlighted_suggestion()
                return
        await super()._on_key(event)


class NoteEditor(Vertical):
    """A TextArea for raw Markdown, with a suggestion list for wiki-links."""

    def __init__(self) -> None:
        super().__init__(id="editor-container")
        self._titles: list[str] = []
        self._link_start: tuple[int, int] | None = None

    def compose(self) -> ComposeResult:
        yield WikiLinkTextArea(id="editor-textarea", soft_wrap=True)
        yield OptionList(id="link-suggestions")

    def on_mount(self) -> None:
        self.query_one("#link-suggestions", OptionList).display = False

    def set_known_titles(self, titles: list[str]) -> None:
        self._titles = titles

    def load_text(self, text: str) -> None:
        area = self.query_one("#editor-textarea", TextArea)
        area.load_text(text)
        area.move_cursor((0, 0))

    def focus_editor(self) -> None:
        self.query_one("#editor-textarea", TextArea).focus()

    @property
    def text(self) -> str:
        return self.query_one("#editor-textarea", TextArea).text

    # -- wiki-link autocomplete -----------------------------------------

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        area = event.text_area
        row, col = area.cursor_location
        line_text = area.get_line(row).plain[:col]
        partial = find_open_link(line_text)
        suggestions = self.query_one("#link-suggestions", OptionList)
        if partial is None:
            suggestions.display = False
            self._link_start = None
            return

        partial_start_col = col - len(partial)  # position right after the opening '[['
        self._link_start = (row, partial_start_col)
        matches = suggest_titles(partial, self._titles)
        suggestions.clear_options()
        if not matches:
            suggestions.display = False
            return
        suggestions.add_options([Option(title, id=title) for title in matches])
        suggestions.highlighted = 0
        suggestions.display = True

    @property
    def suggestions_visible(self) -> bool:
        return self.query_one("#link-suggestions", OptionList).display

    def accept_highlighted_suggestion(self) -> None:
        suggestions = self.query_one("#link-suggestions", OptionList)
        if suggestions.highlighted is not None:
            option = suggestions.get_option_at_index(suggestions.highlighted)
            self._accept_suggestion(str(option.id))
        else:
            suggestions.display = False

    def on_key(self, event) -> None:
        # Note: Enter is handled by WikiLinkTextArea._on_key instead, since
        # TextArea consumes Enter itself before it would bubble here.
        suggestions = self.query_one("#link-suggestions", OptionList)
        if not suggestions.display:
            return
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self.accept_highlighted_suggestion()
        elif event.key == "escape":
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

    def _accept_suggestion(self, title: str) -> None:
        area = self.query_one("#editor-textarea", TextArea)
        suggestions = self.query_one("#link-suggestions", OptionList)
        if self._link_start is None:
            suggestions.display = False
            return
        row, col = area.cursor_location
        area.replace(f"{title}]]", self._link_start, (row, col))
        suggestions.display = False
        self._link_start = None
        area.focus()

    # -- checklist toggling ------------------------------------------------

    def toggle_checkbox_on_current_line(self) -> None:
        area = self.query_one("#editor-textarea", TextArea)
        row, _ = area.cursor_location
        line = area.get_line(row).plain
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith(CHECKBOX_UNCHECKED):
            new_line = indent + CHECKBOX_CHECKED + stripped[len(CHECKBOX_UNCHECKED):]
        elif stripped.startswith(CHECKBOX_CHECKED):
            new_line = indent + CHECKBOX_UNCHECKED + stripped[len(CHECKBOX_CHECKED):]
        elif stripped.startswith("- "):
            new_line = indent + CHECKBOX_UNCHECKED + " " + stripped[2:]
        else:
            new_line = indent + CHECKBOX_UNCHECKED + " " + stripped
        line_len = len(line)
        area.replace(new_line, (row, 0), (row, line_len))
