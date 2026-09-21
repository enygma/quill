"""GFM-style task list ('- [ ]' / '- [x]') helpers.

Shared by the editor (toggling a line with ctrl+t) and the preview
(rendering done items distinctly) -- Textual's Markdown widget has no
built-in GFM task-list support, so a checked item would otherwise show up
as literal, unstyled "[x]" text.
"""

from __future__ import annotations

import re

CHECKBOX_UNCHECKED = "- [ ]"
CHECKBOX_CHECKED = "- [x]"

_CHECKED_LINE_RE = re.compile(r"^(\s*)-\s\[[xX]\]\s?", re.MULTILINE)
_UNCHECKED_LINE_RE = re.compile(r"^(\s*)-\s\[\s\]\s?", re.MULTILINE)


def render_checklists_for_preview(text: str) -> str:
    """Rewrite '- [x] Task' / '- [ ] Task' list items into an obvious
    checkmark / empty box, since they'd otherwise render as literal
    bracket text."""
    text = _CHECKED_LINE_RE.sub(r"\1- ✅ ", text)
    text = _UNCHECKED_LINE_RE.sub(r"\1- ☐ ", text)
    return text
