"""Read-only rendered Markdown preview of the selected note."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Markdown

from ..models import Note
from ..wikilinks import is_wiki_href, render_for_preview

WELCOME = """\
# Welcome to Quill

Select a note from the sidebar, or press `n` to create a new one.
"""


class LinkActivated(Message):
    """A [[wiki link]] or a regular Markdown [link](target) was clicked."""

    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__()


class NotePreview(VerticalScroll):
    """Renders a note's Markdown body, GFM-style, with clickable wiki-links."""

    def compose(self) -> ComposeResult:
        yield Markdown(WELCOME, open_links=False, id="preview-markdown")

    def show_note(self, note: Note | None) -> None:
        md = self.query_one("#preview-markdown", Markdown)
        if note is None:
            md.update(WELCOME)
            return
        pin = "📌 " if note.pinned else ""
        header = f"{pin}**{note.title}**\n\n*Updated {note.updated}*\n\n---\n\n"
        md.update(header + render_for_preview(note.body or "*(empty note)*"))

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        event.prevent_default()
        target = is_wiki_href(event.href)
        if target is None:
            # A regular Markdown [text](target) link, not a [[wiki link]] --
            # still routed through the same activation path (note lookup,
            # or open in the browser for a URL; see App._go_to_link_target).
            target = event.href
        if target:
            self.post_message(LinkActivated(target))
