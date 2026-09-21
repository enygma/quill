"""Optional AI assistant: wraps the Anthropic API with note-editing tools.

This module is only exercised when the `anthropic` package is installed and
an API key is configured; everything else in Quill works without it.
"""

from __future__ import annotations

import os
from typing import Any

from ..config import AIConfig
from ..search import fuzzy_search, text_search
from ..storage import NoteNotFoundError, NoteStore

SYSTEM_PROMPT = (
    "You are the AI assistant embedded in Quill, a terminal note-taking app. "
    "You can search, read, create, and update the user's Markdown notes using "
    "the provided tools. Be concise. When creating or editing notes, prefer "
    "clear Markdown formatting, and use GitHub-style task list syntax "
    "('- [ ] item') for checklists. Note titles can be cross-referenced with "
    "wiki-style links, e.g. [[Other Note Title]]."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_notes",
        "description": "List all notes with their title, path, folder, and pinned status.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_notes",
        "description": "Search notes by text or fuzzy match over title and body.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {"type": "string", "enum": ["text", "fuzzy"], "default": "text"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_note",
        "description": "Read the full contents of a note by its rel_path.",
        "input_schema": {
            "type": "object",
            "properties": {"rel_path": {"type": "string"}},
            "required": ["rel_path"],
        },
    },
    {
        "name": "create_note",
        "description": "Create a new note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string", "default": ""},
                "folder": {"type": "string", "default": ""},
                "pinned": {"type": "boolean", "default": False},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_note",
        "description": "Update an existing note's body, title, and/or pinned status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "rel_path": {"type": "string"},
                "body": {"type": "string"},
                "title": {"type": "string"},
                "pinned": {"type": "boolean"},
            },
            "required": ["rel_path"],
        },
    },
    {
        "name": "delete_note",
        "description": "Delete a note by its rel_path. Use only when the user clearly asked to delete it.",
        "input_schema": {
            "type": "object",
            "properties": {"rel_path": {"type": "string"}},
            "required": ["rel_path"],
        },
    },
]


class AIUnavailableError(Exception):
    pass


class AIProvider:
    def __init__(self, store: NoteStore, config: AIConfig):
        self.store = store
        self.config = config
        self._client = None

    def reconfigure(self, store: NoteStore, config: AIConfig) -> None:
        self.store = store
        self.config = config
        self._client = None

    def _resolve_api_key(self) -> str | None:
        return self.config.api_key or os.environ.get(self.config.api_key_env)

    @property
    def available(self) -> bool:
        if not self.config.enabled:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(self._resolve_api_key())

    def unavailable_reason(self) -> str:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return "The 'anthropic' package isn't installed. Run: pip install quill[ai]"
        if not self.config.enabled:
            return "AI assistant is disabled. Enable it with: quill config set ai.enabled true"
        if not self._resolve_api_key():
            return (
                f"Set the {self.config.api_key_env} environment variable, or run "
                f"'quill config set ai.api_key <key>', to enable the AI assistant."
            )
        return "AI assistant unavailable."

    def _get_client(self):
        import anthropic

        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._resolve_api_key())
        return self._client

    # -- tool execution --------------------------------------------------

    def _execute_tool(self, name: str, tool_input: dict[str, Any]) -> Any:
        try:
            if name == "list_notes":
                return [
                    {
                        "title": n.title,
                        "rel_path": n.rel_path,
                        "folder": n.folder,
                        "pinned": n.pinned,
                    }
                    for n in self.store.list_notes()
                ]
            if name == "search_notes":
                notes = self.store.list_notes()
                mode = tool_input.get("mode", "text")
                results = fuzzy_search(notes, tool_input["query"]) if mode == "fuzzy" else text_search(notes, tool_input["query"])
                return [
                    {"title": r.note.title, "rel_path": r.note.rel_path, "snippet": r.snippet}
                    for r in results[:20]
                ]
            if name == "read_note":
                note = self.store.get(tool_input["rel_path"])
                return {
                    "title": note.title,
                    "rel_path": note.rel_path,
                    "body": note.body,
                    "pinned": note.pinned,
                    "created": note.created,
                    "updated": note.updated,
                }
            if name == "create_note":
                note = self.store.create(
                    title=tool_input["title"],
                    body=tool_input.get("body", ""),
                    folder=tool_input.get("folder", ""),
                    pinned=tool_input.get("pinned", False),
                )
                return {"rel_path": note.rel_path, "title": note.title}
            if name == "update_note":
                note = self.store.get(tool_input["rel_path"])
                if "body" in tool_input:
                    note.body = tool_input["body"]
                if "pinned" in tool_input:
                    note.pinned = tool_input["pinned"]
                if "title" in tool_input and tool_input["title"] != note.title:
                    self.store.rename(note, tool_input["title"])
                self.store.save(note)
                return {"rel_path": note.rel_path, "title": note.title}
            if name == "delete_note":
                self.store.delete(tool_input["rel_path"])
                return {"deleted": tool_input["rel_path"]}
            return {"error": f"Unknown tool: {name}"}
        except NoteNotFoundError:
            return {"error": f"No note found at {tool_input.get('rel_path')!r}"}
        except Exception as exc:  # defensive: never let a tool crash the chat loop
            return {"error": str(exc)}

    # -- chat loop --------------------------------------------------------

    def send(self, history: list[dict[str, Any]], user_message: str) -> tuple[str, list[dict[str, Any]]]:
        """Send a user message, run any tool calls to completion, and return
        (assistant_text, new_history)."""
        if not self.available:
            raise AIUnavailableError(self.unavailable_reason())

        client = self._get_client()
        messages = list(history) + [{"role": "user", "content": user_message}]

        final_text_parts: list[str] = []
        for _ in range(8):  # bound the tool-use loop
            response = client.messages.create(
                model=self.config.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                final_text_parts = [b.text for b in response.content if b.type == "text"]
                break

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }
                    )
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text_parts = ["(stopped after too many tool calls)"]

        return "\n".join(final_text_parts).strip(), messages
