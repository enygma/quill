"""Read-only rendered Markdown preview of the selected note."""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Markdown, Static

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

    DEFAULT_CSS = """
    NotePreview #broken-links-banner {
        display: none;
        background: $error;
        color: $text;
        text-style: bold;
        padding: 0 1;
        width: 100%;
    }
    NotePreview #broken-links-banner.-visible {
        display: block;
    }
    /* CommonMark has no per-link color, so a broken [[wiki link]] is
    rendered as plain inline code (see render_for_preview) instead of a
    link -- re-themed here to red so it actually reads as broken. This
    necessarily re-colors *all* inline code in the preview, not just
    broken-link markers; a reasonable trade given Markdown's limits. */
    #preview-markdown MarkdownBlock > .code_inline {
        background: $error 20%;
        color: $text-error;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="broken-links-banner")
        yield Markdown(WELCOME, open_links=False, id="preview-markdown")

    def show_note(self, note: Note | None, resolve_link: Callable[[str], bool] | None = None) -> None:
        banner = self.query_one("#broken-links-banner", Static)
        md = self.query_one("#preview-markdown", Markdown)
        if note is None:
            banner.remove_class("-visible")
            md.update(WELCOME)
            return
        pin = "📌 " if note.pinned else ""
        header = f"{pin}**{note.title}**\n\n*Updated {note.updated}*\n\n---\n\n"
        body_text, broken = render_for_preview(note.body or "*(empty note)*", resolve=resolve_link)

        if broken:
            names = ", ".join(f"'{t}'" for t in broken)
            plural = "s" if len(broken) != 1 else ""
            banner.update(f"⚠ Broken link{plural}: {names}")
            banner.add_class("-visible")
        else:
            banner.remove_class("-visible")

        md.update(header + body_text)

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
