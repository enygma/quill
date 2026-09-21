"""Docked AI assistant chat panel (optional, Anthropic-backed)."""

from __future__ import annotations

from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Input, Static

from ..ai.provider import AIProvider, AIUnavailableError


class NotesChanged(Message):
    """Posted after a tool call may have mutated notes on disk."""


class AIPanel(Vertical):
    DEFAULT_CSS = """
    AIPanel {
        width: 44;
        border-left: solid $panel;
        display: none;
    }
    AIPanel.-visible {
        display: block;
    }
    #ai-transcript {
        height: 1fr;
        padding: 0 1;
    }
    #ai-input {
        dock: bottom;
    }
    .ai-msg-user {
        color: $text;
        margin-top: 1;
    }
    .ai-msg-assistant {
        color: $success;
        margin-top: 1;
    }
    .ai-msg-system {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self, provider: AIProvider) -> None:
        super().__init__(id="ai-panel")
        self.provider = provider
        self._history: list[dict[str, Any]] = []
        self._thinking_widget: Static | None = None

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="ai-transcript")
        yield Input(placeholder="Ask the AI assistant...", id="ai-input")

    def on_mount(self) -> None:
        if not self.provider.available:
            self._add_message(self.provider.unavailable_reason(), "system")

    def toggle(self) -> None:
        self.set_class(not self.has_class("-visible"), "-visible")
        if self.has_class("-visible"):
            self.query_one("#ai-input", Input).focus()

    def _add_message(self, text: str, role: str, *, thinking: bool = False) -> None:
        if self._thinking_widget is not None:
            self._thinking_widget.remove()
            self._thinking_widget = None
        transcript = self.query_one("#ai-transcript", VerticalScroll)
        prefix = {"user": "You", "assistant": "Claude", "system": "—"}.get(role, role)
        widget = Static(f"[b]{prefix}:[/b] {text}", classes=f"ai-msg-{role}")
        transcript.mount(widget)
        transcript.scroll_end(animate=False)
        if thinking:
            self._thinking_widget = widget

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "ai-input":
            return
        message = event.value.strip()
        if not message:
            return
        event.input.value = ""
        if not self.provider.available:
            self._add_message(self.provider.unavailable_reason(), "system")
            return
        self._add_message(message, "user")
        self._add_message("thinking...", "system", thinking=True)
        self._ask(message)

    @work(thread=True, exclusive=True)
    def _ask(self, message: str) -> None:
        try:
            reply, history = self.provider.send(self._history, message)
        except AIUnavailableError as exc:
            self.app.call_from_thread(self._add_message, str(exc), "system")
            return
        except Exception as exc:  # network/auth errors etc.
            self.app.call_from_thread(self._add_message, f"Error: {exc}", "system")
            return
        self._history = history
        self.app.call_from_thread(self._add_message, reply or "(no response)", "assistant")
        self.app.call_from_thread(self.post_message, NotesChanged())
